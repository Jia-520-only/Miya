// VaM reference plugin with no third-party WebSocket dependency.
// Attach this script to an Atom from Custom/Scripts/Miya.
// It exposes only localhost and queues all VaM work onto Unity's main thread.

using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using SimpleJSON;
using UnityEngine;

namespace MVRPlugin
{
    public class MiyaVAMBridgeTcp : MVRScript
    {
        private const int Port = 8765;
        private const string WebSocketPath = "/miya-vam";
        private const string WebSocketGuid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
        private const int MaxFrameBytes = 1024 * 1024;
        private const float MaxMoveOffset = 0.25f;
        private const float MaxMoveDuration = 5f;

        public string sharedToken = "";
        private TcpListener listener;
        private Thread acceptThread;
        private volatile bool stopping;
        private readonly Queue<MiyaRequest> requests = new Queue<MiyaRequest>();
        private readonly object requestsLock = new object();
        private readonly List<MiyaTcpClient> clients = new List<MiyaTcpClient>();
        private readonly object clientsLock = new object();
        private readonly Dictionary<DAZMorph, float> originalMorphValues = new Dictionary<DAZMorph, float>();
        private readonly Dictionary<EyesControl, EyesControl.LookMode> originalLookModes = new Dictionary<EyesControl, EyesControl.LookMode>();
        private readonly Dictionary<DAZMorph, MorphTransition> morphTransitions = new Dictionary<DAZMorph, MorphTransition>();
        private readonly Dictionary<Transform, Vector3> originalPositions = new Dictionary<Transform, Vector3>();
        private readonly Dictionary<Transform, PositionTransition> positionTransitions = new Dictionary<Transform, PositionTransition>();
        private JSONArray activeSequenceSteps;
        private string activeSequenceId = "";
        private string activeSequenceAtom = "";
        private int activeSequenceIndex;
        private bool activeSequenceLoop;
        private float activeSequenceGap;
        private float nextSequenceAt;

        public override void Init()
        {
            try
            {
                listener = new TcpListener(IPAddress.Loopback, Port);
                listener.Start();
                stopping = false;
                acceptThread = new Thread(AcceptLoop);
                acceptThread.IsBackground = true;
                acceptThread.Start();
                SuperController.LogMessage("Miya VAM Bridge listening on ws://127.0.0.1:" + Port + WebSocketPath);
            }
            catch (Exception ex)
            {
                SuperController.LogError("Miya VAM Bridge failed to start: " + ex.Message);
            }
        }

        public void Update()
        {
            var processed = 0;
            while (processed++ < 16)
            {
                MiyaRequest request = null;
                lock (requestsLock)
                {
                    if (requests.Count > 0) request = requests.Dequeue();
                }
                if (request == null) break;
                try { HandleRequest(request); }
                catch (Exception ex) { request.Client.SendError(request.Id, "command_failed:" + ex.Message); }
            }
            AdvanceMorphTransitions();
            AdvancePositionTransitions();
            AdvanceSequence();
        }

        public void OnDestroy()
        {
            stopping = true;
            if (listener != null)
            {
                try { listener.Stop(); } catch { }
                listener = null;
            }
            lock (clientsLock)
            {
                foreach (var client in clients) client.Close();
                clients.Clear();
            }
        }

        private void AcceptLoop()
        {
            while (!stopping)
            {
                try
                {
                    var tcp = listener.AcceptTcpClient();
                    var client = new MiyaTcpClient(tcp, this);
                    lock (clientsLock) clients.Add(client);
                    client.Start();
                }
                catch
                {
                    if (!stopping) SuperController.LogMessage("Miya VAM Bridge accept loop stopped");
                }
            }
        }

        internal void Enqueue(MiyaRequest request)
        {
            lock (requestsLock) requests.Enqueue(request);
        }

        private void HandleRequest(MiyaRequest request)
        {
            if (!string.IsNullOrEmpty(sharedToken) && request.Token != sharedToken)
            {
                request.Client.SendError(request.Id, "unauthorized");
                return;
            }

            switch (request.Action)
            {
                case "hello":
                    request.Client.SendOk(request.Id, new JSONClass());
                    break;
                case "get_status":
                    var status = new JSONClass();
                    status["plugin"] = "miya-vam-bridge";
                    status["version"] = "0.6.0";
                    status["ready"].AsBool = true;
                    status["scene"] = "";
                    status["allowlistMode"] = "all_scene_persons";
                    status["personCount"].AsInt = CountAllowedPersons();
                    status["activity"] = BuildActivityStatus();
                    status["sceneState"] = BuildSceneState();
                    request.Client.SendOk(request.Id, status);
                    break;
                case "list_atoms":
                    request.Client.SendOk(request.Id, ListAllowedPersons());
                    break;
                case "inspect_person":
                    request.Client.SendError(request.Id, "inspect_person_disabled_to_prevent_heap_exhaustion");
                    break;
                case "get_person_state":
                    request.Client.SendOk(request.Id, GetPersonState(request.Params));
                    break;
                case "set_person_params":
                    request.Client.SendOk(request.Id, SetPersonParams(request.Params));
                    break;
                case "call_person_action":
                    request.Client.SendOk(request.Id, CallPersonAction(request.Params));
                    break;
                case "run_sequence":
                    request.Client.SendOk(request.Id, StartSequence(request.Params));
                    break;
                case "set_expression":
                    request.Client.SendOk(request.Id, SetExpression(request.Params));
                    break;
                case "look_at":
                    request.Client.SendOk(request.Id, SetLookAt(request.Params));
                    break;
                case "move_person":
                    request.Client.SendOk(request.Id, MovePerson(request.Params));
                    break;
                case "stop_all":
                    request.Client.SendOk(request.Id, StopAllMiyaActions());
                    break;
                default:
                    request.Client.SendError(request.Id, "scene_action_not_configured:" + request.Action);
                    break;
            }
        }

        // The bridge deliberately exposes only live Person atoms. This is the
        // dynamic allowlist: character packages are not controllable until the
        // user loads one of them into the current scene as a Person atom.
        private bool IsAllowedPerson(Atom atom)
        {
            return atom != null && !atom.destroyed && atom.type == "Person";
        }

        private int CountAllowedPersons()
        {
            var count = 0;
            var atoms = SuperController.singleton.GetAtoms();
            if (atoms == null) return count;
            foreach (var atom in atoms)
            {
                if (IsAllowedPerson(atom)) count++;
            }
            return count;
        }

        private JSONClass BuildSceneState()
        {
            var result = new JSONClass();
            var user = new JSONClass();
            var cameraTarget = SuperController.singleton.centerCameraTarget;
            var userTransform = cameraTarget != null ? cameraTarget.transform : null;
            var userAvailable = userTransform != null;
            user["available"].AsBool = userAvailable;
            result["user"] = user;

            var persons = new JSONArray();
            var atoms = SuperController.singleton.GetAtoms();
            if (atoms != null)
            {
                foreach (var atom in atoms)
                {
                    if (!IsAllowedPerson(atom)) continue;
                    var item = new JSONClass();
                    item["uid"] = atom.uid ?? "";
                    item["enabled"].AsBool = atom.on;
                    var eyes = FindEyesControl(atom);
                    if (eyes != null) item["lookMode"] = eyes.currentLookMode.ToString();

                    var anchor = GetPersonAnchor(atom);
                    if (userAvailable && anchor != null)
                    {
                        var offset = anchor.position - userTransform.position;
                        var distance = offset.magnitude;
                        item["userDistance"].AsFloat = distance;
                        item["userDistanceKnown"].AsBool = true;
                        var gazeAngle = distance > 0.001f
                            ? Vector3.Angle(userTransform.forward, offset)
                            : 0f;
                        item["userGazeAngle"].AsFloat = gazeAngle;
                        item["userInView"].AsBool = gazeAngle <= 70f;
                    }
                    else
                    {
                        item["userDistanceKnown"].AsBool = false;
                    }
                    persons.Add(item);
                }
            }
            result["persons"] = persons;
            return result;
        }

        private Transform GetPersonAnchor(Atom atom)
        {
            if (atom == null || atom.mainController == null) return null;
            return atom.mainController.control;
        }

        private JSONArray ListAllowedPersons()
        {
            var result = new JSONArray();
            var atoms = SuperController.singleton.GetAtoms();
            if (atoms == null) return result;

            foreach (var atom in atoms)
            {
                if (!IsAllowedPerson(atom)) continue;
                var item = new JSONClass();
                item["uid"] = atom.uid ?? "";
                item["name"] = atom.uid ?? "";
                item["type"] = atom.type ?? "";
                item["enabled"].AsBool = atom.on;
                item["allowed"].AsBool = true;
                result.Add(item);
            }
            return result;
        }

        private Atom ResolveAllowedPerson(string uid)
        {
            if (string.IsNullOrEmpty(uid)) throw new Exception("missing_atom");
            var atom = SuperController.singleton.GetAtomByUid(uid);
            if (atom == null) throw new Exception("atom_not_found:" + uid);
            if (!IsAllowedPerson(atom)) throw new Exception("atom_not_allowed:" + uid);
            return atom;
        }

        private JSONNode MovePerson(JSONClass parameters)
        {
            if (parameters == null) throw new Exception("missing_params");
            var atom = ResolveAllowedPerson(parameters["atom"].Value);
            var control = atom.mainController != null ? atom.mainController.control : null;
            if (control == null) throw new Exception("person_control_not_ready:" + atom.uid);

            var offset = JsonToVector(parameters["offset"], "offset");
            if (Mathf.Abs(offset.x) > MaxMoveOffset || Mathf.Abs(offset.y) > MaxMoveOffset ||
                Mathf.Abs(offset.z) > MaxMoveOffset)
                throw new Exception("move_offset_out_of_range");
            var duration = parameters["duration"].AsFloat;
            if (float.IsNaN(duration) || float.IsInfinity(duration) || duration < 0f || duration > MaxMoveDuration)
                throw new Exception("move_duration_out_of_range");

            if (!originalPositions.ContainsKey(control)) originalPositions[control] = control.position;
            var target = control.position + offset;
            if (duration <= 0f)
            {
                positionTransitions.Remove(control);
                control.position = target;
            }
            else
            {
                positionTransitions[control] = new PositionTransition
                {
                    Control = control,
                    From = control.position,
                    To = target,
                    StartedAt = Time.unscaledTime,
                    Duration = duration
                };
            }

            var result = new JSONClass();
            result["atom"] = atom.uid;
            result["offset"] = VectorToJson(offset);
            result["target"] = VectorToJson(target);
            result["duration"].AsFloat = duration;
            return result;
        }

        private JSONNode InspectPerson(JSONClass parameters)
        {
            if (parameters == null) throw new Exception("missing_params");
            var atom = ResolveAllowedPerson(parameters["atom"].Value);
            var selectedId = parameters["storable"].Value;
            var result = new JSONClass();
            result["atom"] = atom.uid;
            var storables = new JSONArray();
            var ids = atom.GetStorableIDs();
            if (ids == null) ids = new List<string>();

            foreach (var id in ids)
            {
                if (!string.IsNullOrEmpty(selectedId) && id != selectedId) continue;
                var storable = atom.GetStorableByID(id) as JSONStorable;
                if (storable == null) continue;
                var item = new JSONClass();
                item["id"] = id;
                item["type"] = "JSONStorable";
                AddFloatParams(storable, item);
                AddBoolParams(storable, item);
                AddVector3Params(storable, item);
                AddStringParams(storable, item);
                AddStringChooserParams(storable, item);
                AddActions(storable, item);
                storables.Add(item);
            }
            if (!string.IsNullOrEmpty(selectedId) && storables.Count == 0)
                throw new Exception("storable_not_found:" + selectedId);
            result["storables"] = storables;
            return result;
        }

        private JSONNode GetPersonState(JSONClass parameters)
        {
            if (parameters == null) throw new Exception("missing_params");
            var atom = ResolveAllowedPerson(parameters["atom"].Value);
            var selectedId = parameters["storable"].Value;
            if (string.IsNullOrEmpty(selectedId)) throw new Exception("missing_storable_for_state");
            var result = new JSONClass();
            result["atom"] = atom.uid;
            result["readOnly"].AsBool = true;
            var storables = new JSONArray();
            var storable = atom.GetStorableByID(selectedId) as JSONStorable;
            if (storable == null) throw new Exception("storable_not_found:" + selectedId);
            var item = new JSONClass();
            item["id"] = selectedId;
            item["type"] = "JSONStorable";
            AddCurrentFloatParams(storable, item);
            AddCurrentBoolParams(storable, item);
            AddCurrentVector3Params(storable, item);
            AddCurrentStringParams(storable, item);
            AddCurrentStringChooserParams(storable, item);
            AddActions(storable, item);
            storables.Add(item);
            result["storables"] = storables;
            return result;
        }

        private void AddCurrentFloatParams(JSONStorable storable, JSONClass item)
        {
            var values = new JSONClass();
            foreach (var name in storable.GetFloatParamNames())
                values[name].AsFloat = storable.GetFloatParamValue(name);
            item["floats"] = values;
        }

        private void AddCurrentBoolParams(JSONStorable storable, JSONClass item)
        {
            var values = new JSONClass();
            foreach (var name in storable.GetBoolParamNames())
                values[name].AsBool = storable.GetBoolParamValue(name);
            item["bools"] = values;
        }

        private void AddCurrentVector3Params(JSONStorable storable, JSONClass item)
        {
            var values = new JSONClass();
            foreach (var name in storable.GetVector3ParamNames())
                values[name] = VectorToJson(storable.GetVector3ParamValue(name));
            item["vectors"] = values;
        }

        private void AddCurrentStringParams(JSONStorable storable, JSONClass item)
        {
            var values = new JSONClass();
            foreach (var name in storable.GetStringParamNames())
                values[name] = storable.GetStringParamValue(name) ?? "";
            item["strings"] = values;
        }

        private void AddCurrentStringChooserParams(JSONStorable storable, JSONClass item)
        {
            var values = new JSONClass();
            foreach (var name in storable.GetStringChooserParamNames())
                values[name] = storable.GetStringChooserParamValue(name) ?? "";
            item["choices"] = values;
        }

        private void AddFloatParams(JSONStorable storable, JSONClass item)
        {
            var values = new JSONArray();
            foreach (var name in storable.GetFloatParamNames())
            {
                var param = new JSONClass();
                param["name"] = name;
                param["value"].AsFloat = storable.GetFloatParamValue(name);
                param["min"].AsFloat = storable.GetFloatJSONParamMinValue(name);
                param["max"].AsFloat = storable.GetFloatJSONParamMaxValue(name);
                values.Add(param);
            }
            item["floats"] = values;
        }

        private void AddBoolParams(JSONStorable storable, JSONClass item)
        {
            var values = new JSONArray();
            foreach (var name in storable.GetBoolParamNames())
            {
                var param = new JSONClass();
                param["name"] = name;
                param["value"].AsBool = storable.GetBoolParamValue(name);
                values.Add(param);
            }
            item["bools"] = values;
        }

        private void AddVector3Params(JSONStorable storable, JSONClass item)
        {
            var values = new JSONArray();
            foreach (var name in storable.GetVector3ParamNames())
            {
                var param = new JSONClass();
                param["name"] = name;
                param["value"] = VectorToJson(storable.GetVector3ParamValue(name));
                param["min"] = VectorToJson(storable.GetVector3JSONParamMinValue(name));
                param["max"] = VectorToJson(storable.GetVector3JSONParamMaxValue(name));
                values.Add(param);
            }
            item["vectors"] = values;
        }

        private void AddStringParams(JSONStorable storable, JSONClass item)
        {
            var values = new JSONArray();
            foreach (var name in storable.GetStringParamNames())
            {
                var param = new JSONClass();
                param["name"] = name;
                param["value"] = storable.GetStringParamValue(name) ?? "";
                values.Add(param);
            }
            item["strings"] = values;
        }

        private void AddStringChooserParams(JSONStorable storable, JSONClass item)
        {
            var values = new JSONArray();
            foreach (var name in storable.GetStringChooserParamNames())
            {
                var param = new JSONClass();
                param["name"] = name;
                param["value"] = storable.GetStringChooserParamValue(name) ?? "";
                var choices = new JSONArray();
                foreach (var choice in storable.GetStringChooserJSONParamChoices(name))
                    choices.Add(choice);
                param["choices"] = choices;
                values.Add(param);
            }
            item["choices"] = values;
        }

        private void AddActions(JSONStorable storable, JSONClass item)
        {
            var values = new JSONArray();
            foreach (var name in storable.GetActionNames()) values.Add(name);
            item["actions"] = values;
        }

        private JSONNode SetPersonParams(JSONClass parameters)
        {
            if (parameters == null) throw new Exception("missing_params");
            var atom = ResolveAllowedPerson(parameters["atom"].Value);
            var storableId = parameters["storable"].Value;
            if (string.IsNullOrEmpty(storableId)) throw new Exception("missing_storable");
            var storable = atom.GetStorableByID(storableId) as JSONStorable;
            if (storable == null) throw new Exception("storable_not_found:" + storableId);
            var values = parameters["values"] as JSONClass;
            if (values == null || values.Count == 0) throw new Exception("missing_values");
            if (values.Count > 32) throw new Exception("too_many_params");

            var updated = new JSONArray();
            foreach (KeyValuePair<string, JSONNode> pair in values)
            {
                var name = pair.Key;
                var value = pair.Value;
                if (storable.IsFloatJSONParam(name))
                {
                    var number = value.AsFloat;
                    if (float.IsNaN(number) || float.IsInfinity(number)) throw new Exception("invalid_float:" + name);
                    var minimum = storable.GetFloatJSONParamMinValue(name);
                    var maximum = storable.GetFloatJSONParamMaxValue(name);
                    if (number < minimum || number > maximum) throw new Exception("param_out_of_range:" + name);
                    storable.SetFloatParamValue(name, number);
                }
                else if (storable.IsBoolJSONParam(name))
                {
                    storable.SetBoolParamValue(name, value.AsBool);
                }
                else if (storable.IsVector3JSONParam(name))
                {
                    var vector = JsonToVector(value, name);
                    var minimum = storable.GetVector3JSONParamMinValue(name);
                    var maximum = storable.GetVector3JSONParamMaxValue(name);
                    if (vector.x < minimum.x || vector.x > maximum.x ||
                        vector.y < minimum.y || vector.y > maximum.y ||
                        vector.z < minimum.z || vector.z > maximum.z)
                        throw new Exception("param_out_of_range:" + name);
                    storable.SetVector3ParamValue(name, vector);
                }
                else if (storable.IsStringChooserJSONParam(name))
                {
                    var choice = value.Value ?? "";
                    var choices = storable.GetStringChooserJSONParamChoices(name);
                    if (choices == null || !choices.Contains(choice)) throw new Exception("unsupported_choice:" + name);
                    storable.SetStringChooserParamValue(name, choice);
                }
                else if (storable.IsStringJSONParam(name))
                {
                    if (value.Value != null && value.Value.Length > 1024) throw new Exception("string_too_long:" + name);
                    storable.SetStringParamValue(name, value.Value ?? "");
                }
                else
                {
                    throw new Exception("param_not_exposed:" + name);
                }
                updated.Add(name);
            }

            var result = new JSONClass();
            result["atom"] = atom.uid;
            result["storable"] = storableId;
            result["updated"] = updated;
            return result;
        }

        private JSONNode CallPersonAction(JSONClass parameters)
        {
            if (parameters == null) throw new Exception("missing_params");
            var atom = ResolveAllowedPerson(parameters["atom"].Value);
            var storableId = parameters["storable"].Value;
            var action = parameters["action"].Value;
            if (string.IsNullOrEmpty(storableId) || string.IsNullOrEmpty(action))
                throw new Exception("missing_storable_or_action");
            var storable = atom.GetStorableByID(storableId) as JSONStorable;
            if (storable == null) throw new Exception("storable_not_found:" + storableId);
            if (!storable.IsAction(action)) throw new Exception("action_not_exposed:" + action);
            storable.CallAction(action);
            var result = new JSONClass();
            result["atom"] = atom.uid;
            result["storable"] = storableId;
            result["action"] = action;
            result["called"].AsBool = true;
            return result;
        }

        private JSONNode StartSequence(JSONClass parameters)
        {
            if (parameters == null) throw new Exception("missing_params");
            var atom = ResolveAllowedPerson(parameters["atom"].Value);
            var steps = parameters["steps"] as JSONArray;
            if (steps == null || steps.Count == 0) throw new Exception("missing_steps");
            if (steps.Count > 32) throw new Exception("too_many_steps");

            StopSequence("replaced");
            activeSequenceSteps = steps;
            activeSequenceId = Guid.NewGuid().ToString("N");
            activeSequenceAtom = atom.uid;
            activeSequenceIndex = 0;
            activeSequenceLoop = parameters["loop"].AsBool;
            activeSequenceGap = Mathf.Clamp(parameters["gap"].AsFloat, 0f, 60f);
            if (activeSequenceLoop) activeSequenceGap = Mathf.Max(0.5f, activeSequenceGap);
            nextSequenceAt = Time.unscaledTime;
            BroadcastActivity("started", "");

            var result = new JSONClass();
            result["sequenceId"] = activeSequenceId;
            result["atom"] = activeSequenceAtom;
            result["steps"].AsInt = steps.Count;
            result["loop"].AsBool = activeSequenceLoop;
            return result;
        }

        private void AdvanceSequence()
        {
            if (activeSequenceSteps == null || Time.unscaledTime < nextSequenceAt) return;
            if (activeSequenceIndex >= activeSequenceSteps.Count)
            {
                if (!activeSequenceLoop)
                {
                    var completedId = activeSequenceId;
                    ClearSequence();
                    BroadcastActivity("completed", completedId);
                    return;
                }
                activeSequenceIndex = 0;
                nextSequenceAt = Time.unscaledTime + activeSequenceGap;
                BroadcastActivity("loop", "");
                return;
            }

            var step = activeSequenceSteps[activeSequenceIndex] as JSONClass;
            if (step == null)
            {
                StopSequence("invalid_step");
                return;
            }
            try
            {
                ExecuteSequenceStep(step);
                var wait = Mathf.Clamp(step["wait"].AsFloat, 0f, 60f);
                var sequenceAction = step["action"].Value;
                if (sequenceAction == "move_person" || sequenceAction == "set_expression")
                    wait = Mathf.Max(wait, Mathf.Clamp(step["duration"].AsFloat, 0f, 60f));
                activeSequenceIndex++;
                nextSequenceAt = Time.unscaledTime + wait;
                BroadcastActivity("step", "");
            }
            catch (Exception ex)
            {
                var error = ex.Message;
                ClearSequence();
                BroadcastActivity("failed", error);
            }
        }

        private void ExecuteSequenceStep(JSONClass step)
        {
            var action = step["action"].Value;
            var parameters = new JSONClass();
            parameters["atom"] = activeSequenceAtom;
            if (action == "set_expression")
            {
                if (!string.IsNullOrEmpty(step["expression"].Value))
                    parameters["expression"] = step["expression"].Value;
                if (step["morphs"] != null) parameters["morphs"] = step["morphs"];
                if (step["duration"] != null) parameters["duration"] = step["duration"];
                SetExpression(parameters);
            }
            else if (action == "look_at")
            {
                parameters["target"] = step["target"].Value;
                SetLookAt(parameters);
            }
            else if (action == "move_person")
            {
                parameters["offset"] = step["offset"];
                parameters["duration"] = step["duration"];
                MovePerson(parameters);
            }
            else if (action == "set_person_params")
            {
                parameters["storable"] = step["storable"].Value;
                parameters["values"] = step["values"];
                SetPersonParams(parameters);
            }
            else if (action == "call_person_action")
            {
                parameters["storable"] = step["storable"].Value;
                parameters["action"] = step["actionName"].Value;
                CallPersonAction(parameters);
            }
            else
            {
                throw new Exception("unsupported_sequence_action:" + action);
            }
        }

        private JSONNode BuildActivityStatus()
        {
            var result = new JSONClass();
            result["active"].AsBool = activeSequenceSteps != null;
            if (activeSequenceSteps == null) return result;
            result["type"] = "sequence";
            result["sequenceId"] = activeSequenceId;
            result["atom"] = activeSequenceAtom;
            result["step"].AsInt = activeSequenceIndex;
            result["steps"].AsInt = activeSequenceSteps.Count;
            result["loop"].AsBool = activeSequenceLoop;
            return result;
        }

        private void BroadcastActivity(string eventName, string detail)
        {
            var data = new JSONClass();
            data["activity"] = BuildActivityStatus();
            data["event"] = eventName ?? "";
            if (!string.IsNullOrEmpty(detail)) data["detail"] = detail;
            var message = new JSONClass();
            message["type"] = "state_update";
            message["data"] = data;
            lock (clientsLock)
            {
                foreach (var client in clients) client.SendState(message);
            }
        }

        private void StopSequence(string reason)
        {
            if (activeSequenceSteps == null) return;
            ClearSequence();
            BroadcastActivity("stopped", reason);
        }

        private void ClearSequence()
        {
            activeSequenceSteps = null;
            activeSequenceId = "";
            activeSequenceAtom = "";
            activeSequenceIndex = 0;
            activeSequenceLoop = false;
            activeSequenceGap = 0f;
            nextSequenceAt = 0f;
        }

        private JSONClass VectorToJson(Vector3 value)
        {
            var result = new JSONClass();
            result["x"].AsFloat = value.x;
            result["y"].AsFloat = value.y;
            result["z"].AsFloat = value.z;
            return result;
        }

        private Vector3 JsonToVector(JSONNode value, string name)
        {
            var x = value["x"].AsFloat;
            var y = value["y"].AsFloat;
            var z = value["z"].AsFloat;
            if (float.IsNaN(x) || float.IsInfinity(x) ||
                float.IsNaN(y) || float.IsInfinity(y) ||
                float.IsNaN(z) || float.IsInfinity(z))
                throw new Exception("invalid_vector:" + name);
            return new Vector3(x, y, z);
        }

        private JSONNode SetExpression(JSONClass parameters)
        {
            if (parameters == null) throw new Exception("missing_params");
            var atom = ResolveAllowedPerson(parameters["atom"].Value);
            var selector = atom.GetStorableByID("geometry") as DAZCharacterSelector;
            if (selector == null || selector.morphsControlUI == null)
                throw new Exception("person_morphs_not_ready:" + atom.uid);

            var updated = new JSONArray();
            var duration = Mathf.Clamp(parameters["duration"].AsFloat, 0f, 30f);
            var morphs = parameters["morphs"] as JSONClass;
            if (morphs != null && morphs.Count > 0)
            {
                var count = 0;
                foreach (KeyValuePair<string, JSONNode> pair in morphs)
                {
                    if (++count > 16) throw new Exception("too_many_morphs");
                    var morph = FindMorph(selector.morphsControlUI, pair.Key, false);
                    if (morph == null) throw new Exception("morph_not_found:" + pair.Key);
                    ApplyMorph(morph, Mathf.Clamp(pair.Value.AsFloat, -1f, 1f), updated, duration);
                }
            }
            else
            {
                var expression = parameters["expression"].Value;
                if (string.IsNullOrEmpty(expression)) throw new Exception("missing_expression");
                ApplyExpressionAlias(selector.morphsControlUI, expression, updated, duration);
            }

            var result = new JSONClass();
            result["atom"] = atom.uid;
            result["updated"] = updated;
            result["immediate"].AsBool = true;
            return result;
        }

        private JSONNode SetLookAt(JSONClass parameters)
        {
            if (parameters == null) throw new Exception("missing_params");
            var atom = ResolveAllowedPerson(parameters["atom"].Value);
            var eyes = FindEyesControl(atom);
            if (eyes == null) throw new Exception("eyes_control_not_found:" + atom.uid);

            var target = parameters["target"].Value.Trim().ToLowerInvariant();
            EyesControl.LookMode mode;
            if (target == "user" || target == "camera" || target == "player" || target == "用户" || target == "镜头")
                mode = EyesControl.LookMode.Player;
            else if (target == "none" || target == "neutral" || target == "forward" || target == "取消" || target == "前方")
                mode = EyesControl.LookMode.None;
            else
                throw new Exception("unsupported_look_target:" + target);

            if (!originalLookModes.ContainsKey(eyes)) originalLookModes[eyes] = eyes.currentLookMode;
            eyes.currentLookMode = mode;

            var result = new JSONClass();
            result["atom"] = atom.uid;
            result["target"] = target;
            result["mode"] = mode.ToString();
            return result;
        }

        private EyesControl FindEyesControl(Atom atom)
        {
            var ids = atom.GetStorableIDs();
            if (ids == null) return null;
            foreach (var id in ids)
            {
                var eyes = atom.GetStorableByID(id) as EyesControl;
                if (eyes != null) return eyes;
            }
            return null;
        }

        private void ApplyExpressionAlias(GenerateDAZMorphsControlUI morphUi, string expression, JSONArray updated, float duration)
        {
            var key = expression.Trim().ToLowerInvariant();
            if (key == "neutral" || key == "reset" || key == "放松" || key == "恢复")
            {
                RestoreOriginalMorphs(updated);
                return;
            }

            string[] candidates;
            string fallbackKeyword;
            if (key == "smile" || key == "happy" || key == "微笑" || key == "开心")
            {
                candidates = new[] { "Smile Full Face", "Smile Open Full Face", "Smile Simple", "Mouth Smile", "Smile" };
                fallbackKeyword = "smile";
            }
            else if (key == "surprised" || key == "surprise" || key == "惊讶")
            {
                candidates = new[] { "Surprised", "Surprise", "Eyes Wide", "Mouth Open" };
                fallbackKeyword = "surpris";
            }
            else
            {
                candidates = new[] { expression };
                fallbackKeyword = expression;
            }

            DAZMorph morph = null;
            foreach (var candidate in candidates)
            {
                morph = FindMorph(morphUi, candidate, false);
                if (morph != null) break;
            }
            if (morph == null) morph = FindMorph(morphUi, fallbackKeyword, true);
            if (morph == null) throw new Exception("expression_morph_not_found:" + expression);
            ApplyMorph(morph, 0.65f, updated, duration);
        }

        private DAZMorph FindMorph(GenerateDAZMorphsControlUI morphUi, string name, bool contains)
        {
            if (morphUi == null || string.IsNullOrEmpty(name)) return null;
            var direct = morphUi.GetMorphByDisplayName(name) ?? morphUi.GetMorphByUid(name);
            if (direct != null || !contains) return direct;

            var needle = name.ToLowerInvariant();
            var morphs = morphUi.GetMorphs();
            if (morphs == null) return null;
            foreach (var morph in morphs)
            {
                if (morph == null) continue;
                var displayName = morph.resolvedDisplayName ?? "";
                if (displayName.ToLowerInvariant().Contains(needle)) return morph;
            }
            return null;
        }

        private void ApplyMorph(DAZMorph morph, float value, JSONArray updated, float duration)
        {
            if (!originalMorphValues.ContainsKey(morph)) originalMorphValues[morph] = morph.morphValue;
            if (duration <= 0f)
            {
                morph.morphValue = value;
                morphTransitions.Remove(morph);
            }
            else
            {
                morphTransitions[morph] = new MorphTransition
                {
                    Morph = morph,
                    From = morph.morphValue,
                    To = value,
                    StartedAt = Time.unscaledTime,
                    Duration = duration
                };
            }
            var item = new JSONClass();
            item["uid"] = morph.uid ?? "";
            item["name"] = morph.resolvedDisplayName ?? morph.uid ?? "";
            item["value"].AsFloat = value;
            updated.Add(item);
        }

        private void AdvanceMorphTransitions()
        {
            if (morphTransitions.Count == 0) return;
            var finished = new List<DAZMorph>();
            foreach (var pair in morphTransitions)
            {
                var transition = pair.Value;
                if (transition.Morph == null)
                {
                    finished.Add(pair.Key);
                    continue;
                }
                var progress = Mathf.Clamp01((Time.unscaledTime - transition.StartedAt) / transition.Duration);
                transition.Morph.morphValue = Mathf.Lerp(transition.From, transition.To, progress);
                if (progress >= 1f) finished.Add(pair.Key);
            }
            foreach (var morph in finished) morphTransitions.Remove(morph);
        }

        private void AdvancePositionTransitions()
        {
            if (positionTransitions.Count == 0) return;
            var finished = new List<Transform>();
            foreach (var pair in positionTransitions)
            {
                var transition = pair.Value;
                if (transition.Control == null)
                {
                    finished.Add(pair.Key);
                    continue;
                }
                var progress = Mathf.Clamp01((Time.unscaledTime - transition.StartedAt) / transition.Duration);
                transition.Control.position = Vector3.Lerp(transition.From, transition.To, progress);
                if (progress >= 1f) finished.Add(pair.Key);
            }
            foreach (var control in finished) positionTransitions.Remove(control);
        }

        private JSONNode StopAllMiyaActions()
        {
            StopSequence("stop_all");
            morphTransitions.Clear();
            positionTransitions.Clear();
            var restored = new JSONArray();
            RestoreOriginalMorphs(restored);
            var restoredLooks = RestoreOriginalLookModes();
            var restoredPositions = RestoreOriginalPositions();
            var stoppedAnimations = StopPersonAnimations();
            var result = new JSONClass();
            result["restoredMorphs"] = restored;
            result["restoredLooks"] = restoredLooks;
            result["restoredPositions"] = restoredPositions;
            result["stoppedAnimations"].AsInt = stoppedAnimations;
            return result;
        }

        private int StopPersonAnimations()
        {
            var masters = new HashSet<MotionAnimationMaster>();
            var atoms = SuperController.singleton.GetAtoms();
            if (atoms == null) return 0;
            foreach (var atom in atoms)
            {
                if (!IsAllowedPerson(atom) || atom.motionAnimationControls == null) continue;
                foreach (var control in atom.motionAnimationControls)
                {
                    if (control == null) continue;
                    control.playbackEnabled = false;
                    if (control.animationMaster != null) masters.Add(control.animationMaster);
                }
            }
            foreach (var master in masters) master.StopPlayback();
            return masters.Count;
        }

        private JSONArray RestoreOriginalLookModes()
        {
            var restored = new JSONArray();
            foreach (var pair in originalLookModes)
            {
                if (pair.Key == null) continue;
                pair.Key.currentLookMode = pair.Value;
                var item = new JSONClass();
                item["mode"] = pair.Value.ToString();
                restored.Add(item);
            }
            originalLookModes.Clear();
            return restored;
        }

        private void RestoreOriginalMorphs(JSONArray restored)
        {
            morphTransitions.Clear();
            foreach (var pair in originalMorphValues)
            {
                if (pair.Key == null) continue;
                pair.Key.morphValue = pair.Value;
                var item = new JSONClass();
                item["uid"] = pair.Key.uid ?? "";
                item["name"] = pair.Key.resolvedDisplayName ?? pair.Key.uid ?? "";
                item["value"].AsFloat = pair.Value;
                restored.Add(item);
            }
            originalMorphValues.Clear();
        }

        private JSONArray RestoreOriginalPositions()
        {
            var restored = new JSONArray();
            foreach (var pair in originalPositions)
            {
                if (pair.Key == null) continue;
                pair.Key.position = pair.Value;
                var item = new JSONClass();
                item["position"] = VectorToJson(pair.Value);
                restored.Add(item);
            }
            originalPositions.Clear();
            return restored;
        }
    }

    internal sealed class MorphTransition
    {
        public DAZMorph Morph;
        public float From;
        public float To;
        public float StartedAt;
        public float Duration;
    }

    internal sealed class PositionTransition
    {
        public Transform Control;
        public Vector3 From;
        public Vector3 To;
        public float StartedAt;
        public float Duration;
    }

    internal sealed class MiyaRequest
    {
        public MiyaTcpClient Client;
        public string Id;
        public string Action;
        public string Token;
        public JSONClass Params;
    }

    internal sealed class MiyaTcpClient
    {
        private const string WebSocketGuid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
        private const int MaxFrameBytes = 1024 * 1024;
        private readonly TcpClient tcp;
        private readonly MiyaVAMBridgeTcp owner;
        private readonly object sendLock = new object();
        private NetworkStream stream;
        private Thread thread;
        private volatile bool closed;

        public MiyaTcpClient(TcpClient tcp, MiyaVAMBridgeTcp owner)
        {
            this.tcp = tcp;
            this.owner = owner;
        }

        public void Start()
        {
            thread = new Thread(Run);
            thread.IsBackground = true;
            thread.Start();
        }

        public void Close()
        {
            closed = true;
            try { tcp.Close(); } catch { }
        }

        private void Run()
        {
            try
            {
                stream = tcp.GetStream();
                stream.ReadTimeout = 15000;
                if (!Handshake()) return;
                while (!closed)
                {
                    string text;
                    byte opcode;
                    if (!ReadFrame(out opcode, out text)) break;
                    if (opcode == 8) break;
                    if (opcode == 9) SendFrame(10, text ?? "");
                    else if (opcode == 1) EnqueueJson(text);
                }
            }
            catch { }
            finally { Close(); }
        }

        private void EnqueueJson(string text)
        {
            try
            {
                var request = JSON.Parse(text) as JSONClass;
                if (request == null) { SendError("", "invalid_json"); return; }
                var action = request["action"].Value;
                var id = request["id"].Value;
                var token = request["token"].Value;
                var parameters = request["params"] as JSONClass ?? new JSONClass();
                owner.Enqueue(new MiyaRequest { Client = this, Id = id, Action = action, Token = token, Params = parameters });
            }
            catch { SendError("", "invalid_json"); }
        }

        private bool Handshake()
        {
            var headers = ReadHeaders();
            if (headers == null || !headers.ContainsKey("sec-websocket-key")) return false;
            var key = headers["sec-websocket-key"];
            var accept = Convert.ToBase64String(SHA1.Create().ComputeHash(Encoding.UTF8.GetBytes(key + WebSocketGuid)));
            var response = "HTTP/1.1 101 Switching Protocols\r\n" +
                           "Upgrade: websocket\r\nConnection: Upgrade\r\n" +
                           "Sec-WebSocket-Accept: " + accept + "\r\n\r\n";
            var bytes = Encoding.ASCII.GetBytes(response);
            stream.Write(bytes, 0, bytes.Length);
            return true;
        }

        private Dictionary<string, string> ReadHeaders()
        {
            var data = new List<byte>();
            while (data.Count < 8192)
            {
                var value = stream.ReadByte();
                if (value < 0) return null;
                data.Add((byte)value);
                var count = data.Count;
                if (count >= 4 && data[count - 4] == 13 && data[count - 3] == 10 && data[count - 2] == 13 && data[count - 1] == 10) break;
            }
            var text = Encoding.ASCII.GetString(data.ToArray());
            var headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            var lines = text.Split(new[] { "\r\n" }, StringSplitOptions.RemoveEmptyEntries);
            foreach (var line in lines)
            {
                var index = line.IndexOf(':');
                if (index > 0) headers[line.Substring(0, index).Trim()] = line.Substring(index + 1).Trim();
            }
            return headers;
        }

        private bool ReadFrame(out byte opcode, out string text)
        {
            opcode = 0;
            text = null;
            var first = stream.ReadByte();
            var second = stream.ReadByte();
            if (first < 0 || second < 0) return false;
            opcode = (byte)(first & 15);
            var masked = (second & 128) != 0;
            long length = second & 127;
            if (length == 126) length = (stream.ReadByte() << 8) | stream.ReadByte();
            else if (length == 127) return false;
            if (!masked || length < 0 || length > MaxFrameBytes) return false;
            var mask = ReadExact(4);
            var payload = ReadExact((int)length);
            for (var i = 0; i < payload.Length; i++) payload[i] = (byte)(payload[i] ^ mask[i % 4]);
            text = Encoding.UTF8.GetString(payload);
            return true;
        }

        private byte[] ReadExact(int count)
        {
            var data = new byte[count];
            var offset = 0;
            while (offset < count)
            {
                var read = stream.Read(data, offset, count - offset);
                if (read <= 0) throw new IOException("socket_closed");
                offset += read;
            }
            return data;
        }

        public void SendOk(string id, JSONNode data)
        {
            var response = new JSONClass();
            response["id"] = id ?? "";
            response["type"] = "response";
            response["ok"].AsBool = true;
            response["data"] = data ?? new JSONClass();
            SendFrame(1, response.ToString());
        }

        public void SendError(string id, string error)
        {
            var response = new JSONClass();
            response["id"] = id ?? "";
            response["type"] = "response";
            response["ok"].AsBool = false;
            response["error"] = error ?? "unknown_error";
            SendFrame(1, response.ToString());
        }

        public void SendState(JSONNode data)
        {
            SendFrame(1, data != null ? data.ToString() : "{}");
        }

        private void SendFrame(byte opcode, string text)
        {
            if (closed || stream == null) return;
            var payload = Encoding.UTF8.GetBytes(text ?? "");
            if (payload.Length > MaxFrameBytes) return;
            var header = new List<byte> { (byte)(128 | opcode) };
            if (payload.Length < 126) header.Add((byte)payload.Length);
            else { header.Add(126); header.Add((byte)(payload.Length >> 8)); header.Add((byte)payload.Length); }
            lock (sendLock)
            {
                try
                {
                    stream.Write(header.ToArray(), 0, header.Count);
                    stream.Write(payload, 0, payload.Length);
                }
                catch { Close(); }
            }
        }
    }
}
