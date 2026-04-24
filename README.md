# 🤖 QQ群成员动态题验证插件 (group_verification)

<div align="center">
  
![Version](https://img.shields.io/badge/version-26.4.15-blue.svg)
![License](https://img.shields.io/badge/license-AGPLv3-green.svg)
![Platform](https://img.shields.io/badge/platform-AstrBot-purple.svg)

一个智能、高度可定制的QQ群验证工具，通过动态题目有效拦截机器人，保护您的群聊安宁

[功能简介](#features) • [安装方法](#installation) • [配置说明](#configuration) • [使用教程](#usage) • [常见问题](#faq) • [更新日志](#changelog) • [作者及许可](#author)

</div>

> **本项目基于 [huotuo146](https://github.com/huntuo146) 的 [astrbot_plugin_Group-Verification_PRO](https://github.com/huntuo146/astrbot_plugin_Group-Verification_PRO) 修改而来。**
> 在原始版本的基础上增加了分时段验证、LLM 开放题评估、自动审批补验、低 QQ 等级强制验证等大量新功能。

---

<a id="features"></a>
## ✨ 功能简介

本插件为 AstrBot 提供了强大的新成员智能验证功能，能有效过滤广告机器人和可疑用户，全面提升群聊质量。

- 🧠 **动态题目验证**：新成员需回答随机生成的 100 以内加减法问题，亦或是预设好的题目，极大提升验证自由度。
- 🤖 **LLM 开放题评估**：支持使用 LLM 评估开放题答案，用户只需言之有理即可通过，降低机械答题风险。
- 🤖 **自动审批补验**：支持记录进群申请事件，对“申请后 N 分钟内快速通过”的成员追加验证，适配 QQ 自动审批场景。
- 🏢 **分群启用 (White-list)**：支持指定特定群号开启验证，未在名单内的群组将不触发验证流程，更加灵活。
- 🔄 **错误重试机制**：回答错误后自动生成新题并重置计时，给予真实用户改正机会。
- ⏱️ **多段式时间控制**：自定义验证总时长、超时前警告时机、失败后踢出延迟等。
- 🌙 **免验证覆盖**：可配置自动快速通过成员即使命中免验证时段也仍然触发验证。
- � **完全可定制化消息**：欢迎语、错误提示、超时警告、踢出公告等均可自定义，支持丰富变量。
- 🔍 **实时监测**：自动检测进群申请与新成员入群事件，按规则发起验证流程。

---

<a id="configuration"></a>
## ⚙️ 配置说明

### 配置项详情

| 配置项 | 类型 | 说明 |
| :--- | :--- | :--- |
| `enabled_groups` | list | **启用插件的群号列表**。留空则全局生效，否则仅对名单内的群生效。 |
| `verification_timeout` | int | 验证总超时时间（秒），默认 `300`。 |
| `auto_approval_verify_only` | bool | 是否在免验证时段仅验证“申请后短时间内自动通过”的成员，默认 `false`。 |
| `auto_approval_window_minutes` | int | 自动快速通过判定窗口（分钟），默认 `1`。 |
| `join_request_cache_ttl_seconds` | int | 进群申请事件缓存保留时长（秒），默认 `360`。 |
| `auto_approval_ignore_time_based_bypass` | bool | 自动快速通过成员是否忽略免验证时段，默认 `true`。 |
| `auto_approval_lookup_system_msg` | bool | 入群时是否调用 `get_group_system_msg` 作为自动审批识别兜底，默认 `true`。 |
| `auto_approval_system_msg_retry_delay` | float | 系统消息兜底重试延迟秒数，默认 `1.0`。 |
| `auto_approval_nickname_match` | bool | 是否允许用昵称辅助识别自动快速通过成员，默认 `true`。 |
| `low_qq_level_force_verify_threshold` | int | 低 QQ 等级强制验证阈值。设为 `-1` 关闭；设为 `0` 时仅 0 级 QQ 强制验证。 |
| `low_qq_level_force_verify_timeout` | int | 低 QQ 等级强制验证专用超时时间（秒）。设为 `-1` 时回退到 `verification_timeout`。 |
| `kick_countdown_warning_time` | int | 超时前发送警告秒数，设为 `0` 可禁用，默认 `60`。 |
| `kick_delay` | int | 发送“验证超时”消息后延迟踢出秒数，默认 `5`。 |
| `allow_answer_without_at` | bool | 是否允许待验证成员不 @ 机器人直接作答，默认 `false`。开启后会保留原有 @ 方式，同时额外接受直接发送的答案。 |
| `wrong_answer_bypass_behavior` | string | 答错后若命中免验证时段时的处理方式，支持 `pass` 与 `continue`，默认 `pass`。 |
| `llm_question_enabled` | bool | 是否启用 LLM 开放题评估功能，默认 `false`。 |
| `llm_provider_id` | string | LLM 评估使用的模型 ID，留空则使用当前会话默认模型。 |
| `llm_evaluation_timeout` | int | LLM 评估请求超时时间（秒），默认 `30`。 |
| `llm_error_behavior` | string | LLM 调用错误时的处理方式，`pass`=放行，`retry_math`=切换数学题，默认 `pass`。 |
| `llm_timeout_buffer` | int | LLM 评估超时缓冲时间（秒），默认 `120`。 |
| `llm_system_prompt` | string | LLM 评估系统提示词模板。 |
| `llm_evaluation_prompt` | string | LLM 评估用户回答的提示词模板。 |
| `new_member_prompt` | string | 新成员入群时发送的欢迎及验证提示语。 |
| `welcome_message` | string | 验证成功后的祝贺提示语。 |
| `bypass_welcome_message` | string | 答错后因免验证放行时发送的欢迎提示语。 |
| `wrong_answer_prompt` | string | 回答错误后的提示语（自动附带新题）。 |
| `failure_message` | string | 验证失败前的“最后通牒”消息。 |
| `kick_message` | string | 成员被踢出后在群内的公开通知。 |

### 支持的模板变量

- `{at_user}` — @目标用户 的 CQ 码
- `{member_name}` — 用户的群名片或 QQ 昵称
- `{question}` — 随机生成的数学题 (例如 `76 + 24 = ?`)
- `{timeout}` — 验证超时时长（分钟）
- `{countdown}` — 踢出前的延迟秒数

---

<a id="usage"></a>
## 📝 使用教程

1. **白名单设置**：在 `enabled_groups` 中填入需要开启验证的群号。若保持为空，则插件会对机器人加入的所有群组生效。
2. **默认模式**：当 `auto_approval_verify_only=false` 时，所有新成员仍按 `time_based_timeouts` 的时间段规则决定是否验证。
3. **低等级强制验证优先**：若启用了 `low_qq_level_force_verify_threshold`，插件会在新成员入群时调用 NapCat 的 `get_stranger_info` 查询 `qqLevel`。当 `qqLevel` 小于或等于阈值时，将直接强制验证，并忽略分时段免验证与自动审批放行规则。
4. **自动审批补验模式**：当成员未命中低等级强制验证，且 `auto_approval_verify_only=true` 时，机器人会优先使用 `request/group/add` 申请事件缓存；若未命中，还会在入群时调用 `get_group_system_msg` 兜底查询审核记录。当前处于免验证时段时，只有该成员在 `auto_approval_window_minutes` 分钟内入群，才视为自动快速通过并触发补验。
5. **昵称辅助匹配**：若系统消息里的 `invitor_uin` 不能稳定代表申请人，插件会结合 `requester_nick`、`invitor_nick` 与当前入群昵称做评分匹配；并可通过 `auto_approval_system_msg_retry_delay` 在列表未及时同步时重试一次。
6. **夜间全体验证**：如果当前时间段本身配置为需要验证（例如 `23:01-07:29=660`），那么即使开启 `auto_approval_verify_only`，所有新成员也仍会按该超时时间正常验证。
7. **免验证时段覆盖**：若开启 `auto_approval_ignore_time_based_bypass`，则自动快速通过成员即使命中分时免验证规则，也会按默认超时时间继续验证。
8. **答错后命中免验证时段的处理**：若 `wrong_answer_bypass_behavior=pass`，则会结束当前验证流程、按配置撤回待验证期间消息，并发送 `bypass_welcome_message`；若为 `continue`，则当前会话会继续执行，不因时段切换而中断。
9. **LLM 开放题使用**：在 `custom_qa` 中添加以 `llm:` 开头的题目，格式为 `llm:你认为Minecraft是什么样的游戏？=开放世界、自由度高、言之有理即可`。开启 `llm_question_enabled` 后，此类题目将调用 LLM 评估用户回答是否合理。LLM 开放题会自动增加超时缓冲时间（`llm_timeout_buffer`），避免评估耗时导致误超时。
9. **免 @ 模式**：若开启 `allow_answer_without_at`，则会保留原有 @ 验证方式，同时允许待验证成员直接发送答案完成验证，无需额外 @ 机器人。
10. **容错机制**：如果成员回复错误，系统会提示错误并立即更换题目，重新开始计时，避免因手抖导致的误踢。
11. **清理逻辑**：如果成员在验证期间主动退群、超时被踢，或答错后命中免验证时段提前结束，系统都会统一清理待验证状态，并按配置撤回已记录的未验证期间消息。

---

<a id="faq"></a>
## ❓ 常见问题

- **Q: 为什么输入正确答案没反应？** A: 默认情况下请确保回复时 **@了机器人**。如果希望新成员无需 @ 机器人也能验证，请在配置中开启 `allow_answer_without_at`。
- **Q: 开启自动审批补验后，为什么白天有些新成员没有被验证？** A: 当 `auto_approval_verify_only=true` 且当前命中免验证时段时，仅会验证“先收到进群申请事件，或可从 `get_group_system_msg` 查询到已处理审核记录，且在窗口时间内完成入群”的成员。若平台未上报申请事件，系统消息列表里也查不到对应记录，或人工审核耗时超过窗口值，则不会命中补验规则。
- **Q: `get_group_system_msg` 里的 `invitor_uin` 不稳定怎么办？** A: 当前版本会优先使用 QQ 强匹配；若 `invitor_uin` 语义不稳定，还会结合 `requester_nick`、`invitor_nick`、当前入群昵称与 `request_id` 时间做评分匹配，并支持一次短延迟重试，以适配 NapCat 的实际返回差异。
- **Q: 自动审批成员命中了免验证时间段，为什么还是被验证？** A: 如果开启了 `auto_approval_ignore_time_based_bypass`，自动快速通过成员会忽略免验证时段，按默认超时时间继续验证，这是为了专门覆盖 QQ 自动审批场景。
- **Q: 为什么有些 0 级或低等级 QQ 白天也会被强制验证？** A: 如果启用了 `low_qq_level_force_verify_threshold`，当 NapCat `get_stranger_info` 返回的 `qqLevel` 小于或等于该阈值时，成员会直接进入强制验证流程，并忽略分时段免验证与自动审批放行规则。
- **Q: `get_stranger_info` 查询失败了怎么办？** A: 当前策略是安全回退：若无法获取 `qqLevel`，插件不会因查询失败而强制验证，而是回退到原有自动审批补验/分时段规则继续处理。
- **Q: 答错后正好切到免验证时段，为什么有人会继续答题、有人会直接放行？** A: 这取决于 `wrong_answer_bypass_behavior`。设为 `pass` 时会结束当前验证流程并发送 `bypass_welcome_message`；设为 `continue` 时，只要该成员已经进入验证流程，就会继续完成当前会话。
- **Q: 机器人没有踢人权限？** A: 请确保机器人帐号拥有 **群管理员** 或 **群主** 权限。
- **Q: 如何彻底关闭某个群的验证？** A: 如果你设置了 `enabled_groups`，只需将该群号移出列表；如果列表为空，则需要在 AstrBot 插件管理中禁用本插件。

---

<a id="changelog"></a>
### LLM 开放题格式

在 `custom_qa` 配置中添加 LLM 开放题，格式如下：

```
llm:题目内容=关键词1、关键词2、引导语
```

示例：
```
llm:你认为Minecraft是什么样的游戏？=开放世界、自由度高、言之有理即可
llm:你最喜欢哪个季节？=春天、夏天、秋天、冬天、季节
```

- `llm:` 前缀标识该题目需要 LLM 评估
- `=` 左侧是题目内容（展示给用户）
- `=` 右侧是关键词/引导语，供 LLM 评估时参考

## 📋 更新日志

### v26.4.23 - 2026-04-15
* [新增] 新增新用户发无关验证消息自动撤回。
* [移除] 移除原有退群全部消息撤回逻辑。
* [优化] 加群流程之后，事件仍继续传播。

### v26.4.16 - 2026-04-15
* [优化] 将 LLM 开放题与问答题放入相同概率池中。

### v26.4.15 - 2026-04-15
* [新增] 新增 LLM 开放题评估功能，支持使用 LLM 判断用户回答是否合理。
* [新增] 新增 `llm_question_enabled`、`llm_provider_id`、`llm_evaluation_timeout`、`llm_error_behavior`、`llm_timeout_buffer`、`llm_system_prompt`、`llm_evaluation_prompt` 配置项。
* [新增] 题库支持 `llm:` 前缀标识开放题，格式为 `llm:题目=关键词`。
* [优化] LLM 开放题自动增加超时缓冲时间，避免评估耗时导致误超时。
* [优化] 答错后命中免验证时段时不再撤回用户发言。

### v26.4.13 - 2026-04-12
* [新增] 新增 `low_qq_level_force_verify_threshold` 配置项，可基于 NapCat `get_stranger_info` 返回的 `qqLevel` 对低等级 QQ 成员强制发起验证。
* [新增] 新增 `low_qq_level_force_verify_timeout` 配置项，可为低等级强制验证单独设置超时时长；设为 `-1` 时回退使用默认 `verification_timeout`。
* [优化] 低等级强制验证优先级高于自动审批补验与分时段免验证规则，更适合针对 0 级等高风险新号做兜底验证。
* [健壮性] 当 `get_stranger_info` 查询失败或未返回有效 `qqLevel` 时，自动回退到原有验证逻辑，避免因 API 抖动导致全员误触发强制验证。

### v26.4.12 - 2026-04-12
* [新增] 新增 `wrong_answer_bypass_behavior` 配置项，可选“答错后命中免验证时段时直接放行”或“继续完成当前验证流程”。
* [新增] 新增 `bypass_welcome_message` 配置项，用于在答错后因免验证放行时发送明确欢迎提示，避免群内误解。
* [优化] 已开始的验证会话会记录当前会话超时时长，便于在 `continue` 模式下保持会话行为稳定。

### v26.4.11 - 2026-04-11
* [关键修复] 将消息事件处理优先级提升至 `10000`，确保待验证用户的回答消息能被优先处理，避免被其他对话插件拦截导致验证失败和误踢。

### v26.4.10 - 2026-04-09
* [优化] `get_group_system_msg` 兜底识别新增昵称辅助评分匹配与一次短延迟重试，提升 NapCat 自动审批场景下的识别成功率。
* [优化] 统一 pending 清理逻辑，覆盖验证成功、成员离群、超时踢出、答错后命中免验证时段等路径。
* [优化] 待验证期消息跟踪逻辑统一封装，提升未验证期间消息撤回的一致性。
* [新增] 新增 `auto_approval_system_msg_retry_delay`、`auto_approval_nickname_match` 配置项。

### v26.4.9 - 2026-04-09
* [新增] 支持监听 QQ `request/group/add` 进群申请事件，并可在入群时调用 `get_group_system_msg` 兜底识别“申请后短时间内自动通过”的成员。
* [新增] 新增 `auto_approval_verify_only`、`auto_approval_window_minutes`、`join_request_cache_ttl_seconds`、`auto_approval_ignore_time_based_bypass`、`auto_approval_lookup_system_msg` 配置项。
* [优化] 自动快速通过成员可配置忽略分时免验证规则，专门覆盖 QQ 自动审批场景。

### ​v2.1.2 (2026-2-11）
​此版本重点解决了在复杂网络环境下或接收特殊事件时插件崩溃的问题。
* ​🐛 修复：解决了在处理非标准事件时，由于 raw_message 为空导致的 'NoneType' object has no attribute 'get' 严重报错。
* ​🔧 优化：将事件过滤器调整为 EventMessageType.ALL，确保能更稳健地捕获入群通知（Notice）事件。
* ​🛡️ 健壮性：增加了防御性编程检查，确保在数据异常或平台 API 调用失败时插件不会崩溃，并能记录错误日志。

### v2.1.0 - 2025-12-21
* [新增] **分群启用功能**：新增 `enabled_groups` 配置项，支持设置白名单模式。
* [优化] 完善数学题重试逻辑，确保每次回答错误后生成的题目具有随机性。
* [优化] 更新所有说明文档以匹配最新白名单逻辑。

### v1.0.4 - 2025-08-08
* [关键修复] 解决了因 `from astrbot.api.bot import Bot` 语句在部分版本中不兼容导致的 `ModuleNotFoundError` 问题。
* [兼容性] 移除特定导入和类型提示，确保在不同 AstrBot 版本中加载成功。

### v1.0.3 - 2025-08-07
* [修复] 修复了 `_timeout_kick` 函数中存在的不完整代码行导致的语法错误。

### v1.0.2 - 2025-08-07
* [健壮性] 重构消息格式化逻辑，即使模板缺少占位符（如 `{member_name}`）也不会导致插件崩溃。
* [优化] 升级答案提取算法，智能识别用户回复中的数字，提高识别准确率。
* [解耦] 移除平台硬编码，不再硬编码 `aiocqhttp` 平台，为未来适配其他 OneBot 实现打下基础。

### v1.0.1 - 2025-08-07
* [重大升级] 核心验证方式从静态关键词升级为 **100以内动态数学题验证**。
* [功能] 新增验证超时前警告、错误重试、自定义踢出延迟功能。
* [重构] 优化验证逻辑与状态管理，提升并发处理稳定性。

---

<a id="author"></a>
## 👤 作者及许可

- **原始作者**：[huotuo146](https://github.com/huntuo146)
- **修改者**：SodaTide
- **原始项目**：[astrbot_plugin_Group-Verification_PRO](https://github.com/huntuo146/astrbot_plugin_Group-Verification_PRO)
- **当前项目**：[group_verification](https://github.com/huntuo146/astrbot_plugin_Group-Verification_PRO)（基于原始项目修改）

本项目基于 huotuo146 的 [astrbot_plugin_Group-Verification_PRO](https://github.com/huntuo146/astrbot_plugin_Group-Verification_PRO) 修改，
继续采用 [AGPLv3 许可证](LICENSE) 开源。

---

<div align="center">
<p>如果您觉得这个插件有用，请考虑给项目一个 ⭐Star！</p>
<sub>Original by huotuo146 • Modified by SodaTide</sub>
</div>

---

<div align="center">

### 🤖 致谢

本项目在开发过程中大量借助 AI 辅助编程（Vibe Coding），
感谢 GPT 等大语言模型为代码编写提供的强大支持！

</div>
