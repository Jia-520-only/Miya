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
                    status["version"] = "0.5.0";
                    status["ready"].AsBool = true;
                    status["scene"] = "";
                    status["allowlistMode"] = "all_scene_persons";
                    status["personCount"].AsInt = CountAllowedPersons();
                    request.Client.SendOk(request.Id, status);
                    break;
                case "list_atoms":
                    request.Client.SendOk(request.Id, ListAllowedPersons());
                    break;
                case "set_expression":
                    request.Client.SendOk(request.Id, SetExpression(request.Params));
                    break;
                case "look_at":
                    request.Client.SendOk(request.Id, SetLookAt(request.Params));
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

        private JSONNode SetExpression(JSONClass parameters)
        {
            if (parameters == null) throw new Exception("missing_params");
            var atom = ResolveAllowedPerson(parameters["atom"].Value);
            var selector = atom.GetStorableByID("geometry") as DAZCharacterSelector;
            if (selector == null || selector.morphsControlUI == null)
                throw new Exception("person_morphs_not_ready:" + atom.uid);

            var updated = new JSONArray();
            var morphs = parameters["morphs"] as JSONClass;
            if (morphs != null && morphs.Count > 0)
            {
                var count = 0;
                foreach (KeyValuePair<string, JSONNode> pair in morphs)
                {
                    if (++count > 16) throw new Exception("too_many_morphs");
                    var morph = FindMorph(selector.morphsControlUI, pair.Key, false);
                    if (morph == null) throw new Exception("morph_not_found:" + pair.Key);
                    ApplyMorph(morph, Mathf.Clamp(pair.Value.AsFloat, -1f, 1f), updated);
                }
            }
            else
            {
                var expression = parameters["expression"].Value;
                if (string.IsNullOrEmpty(expression)) throw new Exception("missing_expression");
                ApplyExpressionAlias(selector.morphsControlUI, expression, updated);
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

        private void ApplyExpressionAlias(GenerateDAZMorphsControlUI morphUi, string expression, JSONArray updated)
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
            ApplyMorph(morph, 0.65f, updated);
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

        private void ApplyMorph(DAZMorph morph, float value, JSONArray updated)
        {
            if (!originalMorphValues.ContainsKey(morph)) originalMorphValues[morph] = morph.morphValue;
            morph.morphValue = value;
            var item = new JSONClass();
            item["uid"] = morph.uid ?? "";
            item["name"] = morph.resolvedDisplayName ?? morph.uid ?? "";
            item["value"].AsFloat = value;
            updated.Add(item);
        }

        private JSONNode StopAllMiyaActions()
        {
            var restored = new JSONArray();
            RestoreOriginalMorphs(restored);
            var restoredLooks = RestoreOriginalLookModes();
            var result = new JSONClass();
            result["restoredMorphs"] = restored;
            result["restoredLooks"] = restoredLooks;
            return result;
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
