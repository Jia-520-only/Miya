# Platform Capabilities

Capabilities below describe supported message paths. A platform's ability to reply to an inbound event does not imply that it can receive unattended proactive messages.

| Adapter | Inbound chats | Proactive text | Outbound media | Notes |
| --- | --- | --- | --- | --- |
| OneBot / NapCat (`aiocqhttp`) | Private, group | Private, group | Images and files through OneBot APIs | Social actions depend on the OneBot implementation and permissions. |
| QQ Official (`qqofficial`) | C2C, group, channel, channel direct | C2C and group APIs | Image, video, and Silk through upload APIs; C2C/group only | Channel and channel-direct responses use the original event reply method. Channel reactions are distinct from group/C2C reactions. |
| WeChat Official Account (`weixin_official_account`) | Private webhook | Disabled as a general proactive target by default | Inbound image/voice; outbound media is not implemented here | Inbound replies can be passive within the webhook response window. Optional customer-service sending is controlled separately by `active_send_mode` and platform eligibility. |
| WeChat iLink (`weixin_ilink`) | Private polling | Private | Image and file | Outbound media is serialized per account; inbound image, voice, file, and video can be downloaded when available. |
| WeChat Open Platform (`weixin_oc`) | Private polling | Private text | Inbound image/file handling; outbound text only | Uses token-authenticated polling and send APIs. |
| WeCom (`wecom`) | Private webhook | No general proactive sender in this adapter | Inbound image/voice; outbound text reply | Replies use the configured enterprise agent and webhook event. |

`support_proactive_message` is an adapter-level opt-out for unattended delivery. The sender must also exist for the requested chat type. Explicit platform routing still preserves the original platform and target; cross-platform selection is a separate routing decision.

The QQ and WeChat API behavior remains subject to account permissions, message windows, and SDK/API responses. This table records the current adapter implementation, not a guarantee from the external platform.
