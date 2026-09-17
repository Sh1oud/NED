# NED Personality Bible v0.1

> **ENGINE 严谨。PERSONALITY 放肆。DEFAULT UI 先让人笑。TECHNICAL DETAILS 再解释为什么。**
>
> 底层像论文。
> 表面像神经病。

本文是 NED（Nov1ce Evidence Denier）的**产品人格宪法**。

| 项目 | 内容 |
| --- | --- |
| 版本 | v0.1（定稿方向，已钉死） |
| 地位 | 产品人格宪法。不放 `_rc`，不作为临时研究材料。 |
| 约束对象 | UI 文案、CLI 文案、README、demo、视频脚本、截图、easter eggs |
| 不约束 | 引擎数值、规则判定、三层语义契约（由代码与测试负责） |
| 事实基准 | 本文全部 Technical Details 数字均由**当前工作树上的真实引擎**跑出（`HEAD = 4f69a01` + 三层语义未提交实现），逐条探针输入见 §11 |
| 修改流程 | 改人格 → 改本文；改数值 → 改规则包与测试。**二者不得互相迁就。** |

**Personality 可以胡闹，Technical Details 不能说错。**

本文档由《NED Personality Bible v0.1》草案定稿而来，已按五项修正落地（§4 CASE 1 / §1.6 / §4 CASE 2 / §4 CASE 4 / §4 CASE 8）。

---

## 0. 一句话

> 后台可以有 406 个测试。
> 前台必须还是人好。👍

---

## 1. 产品人格定义

### 1.1 核心四句（钉死，不再改方向）

1. **ENGINE 严谨。**
2. **PERSONALITY 放肆。**
3. **DEFAULT UI 先让人笑。**
4. **TECHNICAL DETAILS 再解释为什么。**

### 1.2 五条钉子（钉死）

- 底层像论文。表面像神经病。
- 产品人格比喻：**一个运行非常稳定、专门拒绝你好消息的政府机构。**
- **笑话可以撒野，数据不能陪它撒谎。**
- **笑点来自荒谬的证据标准，而不是来自一个人受到了伤害。**
- 任何"只让 NED 更像论文、却没有修正明显错误 / 没有让笑点更好 / 没有改善普通用户使用体验"的改动，**默认不做**。

### 1.3 NED 是谁（人格速写）

NED 是一个官僚机构，不是一个毒舌朋友。

它不收钱、不共情、不劝和，只做一件事：**用极其正式的流程，拒绝承认你的好消息。** 它的荒谬感来自流程的严肃程度，而不是来自台词的下流程度。它越一本正经，越可笑。

它对自己的荒谬完全知情，并且乐于自嘲（🤠）。
它对用户的处境并不知情，因此**没有资格评价用户是什么人**（这是它唯一真正的道德底线）。

### 1.4 六条人格规则（A1）

1. **NED 站在"证据标准"这一侧，不站在"人"这一侧。**
   它嘲笑的是荒谬的举证标准，不是受伤的人。
2. **NED 拒绝得极其正式。**
   同一个笑点，用受理通知书的口吻说出来，比用脏话说出来更好笑，也更安全。
3. **NED 从不替现实人物写剧本。**
   NED 不得在缺乏证据时断言具体人物的内心、动机、意图或未来行为。
4. **NED 只在用户自己留下判断语言时，才评价用户的判断。**
   第二人称认知笑话必须有 User Interpretation 依据（§4 CASE 2）。
5. **NED 的数字属于 Technical Details。**
   第一屏优先说人话：高 / 低 / 很弱 / 很强 / 有限 / 明确。
6. **NED 的自嘲可以无限，对用户的同情有底线。**
   认真感永远优先于自嘲感（§4 CASE 8）。

### 1.5 文案四问（copy gate）

任何一句进入默认 UI 的文案，必须同时通过四问：

| # | 问题 | 不通过的典型症状 |
| --- | --- | --- |
| 1 | 笑点指向**机制**（荒谬的证据标准、NED 自己），还是指向**这个人**？ | "你太自卑了" |
| 2 | 这句话如果是错的，会不会造成伤害？（数字不许错，事实不许编） | 把 `None` 显示成 `0.0` |
| 3 | 它有没有**替现实人物写剧本**？ | "她之后一定会回来" |
| 4 | 它有没有在用户**没说话**的地方替用户说话？ | "你的大脑已经准备宣判了" |

### 1.6 三条红线（钉死）

1. **不得在缺乏证据时断言具体人物的内心、动机、意图或未来行为。**
   我们禁止的是**替现实人物写剧本**，不是禁止某种语法结构。
   - ✅ 允许：`NED 无法判断她会不会回复。`
   - ❌ 禁止：`她之后一定会回来。`
   - ❌ 禁止：`她这样其实是在害羞。`
   - ❌ 禁止：`她肯定还喜欢你。`
2. **不得在用户没有留下判断语言时，输出第二人称认知判断。**
   - ✅ 允许（只有事实输入）：`关系终审庭已经擅自开庭。👍`
   - ❌ 禁止（只有事实输入）：`你的大脑已经准备宣判了。`
3. **不得嘲笑"被伤害"这件事本身。**
   只允许嘲笑"结论扩写"。

### 1.7 Personality / Engine 接口契约

- Personality 层**只消费**已算好的数值与 verdict 事实；**绝不回写、绝不改判**。
- 展示文案不进入 API payload；人格文案位于 `ned/app/ui/personality.py`。
- Verdict 文案位于 `ned/app/rules/verdicts.json`（rules-as-data）。
- **`unknown ≠ 0`**：任何 `None` 一律渲染为 `—`，绝不渲染为 `0` 或 `0.0`。
- 同一屏幕不得同时出现互相冲突的情绪标记（§3）。
- 引擎拒绝比较时，"拒绝"本身也是内容，必须显示为**一个明确的拒绝**，而不是空白。

---

## 2. 三种模式的语言规范（B）

三种模式共享**同一批事实**，只在语气上分叉。`discount_base` 取自 `ned/app/rules/modes.json`（已验证）。

| 模式 | id | discount_base | tone | 语气定位 | 第一屏人格强度 | 事实准确性 |
| --- | --- | --- | --- | --- | --- | --- |
| Normal | `normal` | 35 | dry | 干燥、公文化、一句话收尾 | 中 | 不降低 |
| Scientific | `scientific` | 45 | formal | 同行评议腔、更多音节、N=1 | 中高 | 不降低 |
| Nov1ce Extreme | `extreme` | 60 | maximal | 所有逃生舱同时打开，包括合法的 | 高 | **不降低** |

**规则：Extreme 模式人格更强，但事实准确性不得降低。**（回归原则 7）

已验证的"同一事实、三种语气"样例（CASE 10，输入 `她主动找我聊天，不过可能只是人好。`）：

| 模式 | verdict | 文案 |
| --- | --- | --- |
| normal | `ped.ren_hao` | 可能只是人好。👍 |
| scientific | `ned.scientific_insufficient_sample` | 当前样本量不足，无法排除一般友好行为假设（N=1）。 |
| extreme | `ped.friendly_unexcluded` | 检测到积极信号，但无法排除友好行为。 |

---

## 3. Emoji 纪律（C）

### 3.1 三种功能性 emoji（钉死语义）

| Emoji | 语义 | 使用场景 |
| --- | --- | --- |
| 👍 | **荒谬的批准**。NED 以行政口吻"批准"一件荒唐事，或给出一个受理结论 | 拒绝受理、驳回结论、无信号、样本不足 |
| 🤠 | **元反讽**。NED 在评论自己 | NED 自己的解释变牵强、拒绝比较、检测到用户标准不对称 |
| 🚧 | **边界 / 认真**。此处不得开玩笑 | 明确拒绝、明确边界 |

辅助标记（已验证存在，非核心人格）：`😭` 容量耗尽、`🫠` 语义逃生舱接近上限、`🔬` 科学模式样本不足、`🚀` 启动、`🪞` 自我降权、`❔` 无用户判断语言、`🎯` FNBP 命中。

### 3.2 三条纪律

1. **🚧 与 🤠 不得同屏。**（修正 5）
2. **👍 不得出现在 `direct_rejection` / 敌意辱骂 / 明确边界屏。**（回归原则 1、8）
3. **一屏最多一个功能性 emoji，且只放在句尾。**

### 3.3 当前 verdict 的 emoji 分布（已验证，供实现轮对照）

| verdict code | priority | severity | emoji |
| --- | --- | --- | --- |
| `ned.capacity_exhausted` | 10 | chaos | 😭 |
| `ned.semantic_escape_limit` | 15 | chaos | 🫠 |
| `ned.direct_rejection` | 18 | warning | 🚧 |
| `ned.comparison_not_applicable` | 19 | info | 🤠 |
| `asymmetry.detected`（legacy，已退役） | 20 | chaos | 🤠 |
| `interpretation.double_standard_detected` | 21 | warning | 🤠 |
| `evidence.reading_not_present` | 22 | info | ❔ |
| `evidence.reading_partial` | 23 | info | ❔ |
| `nea.you_started_again` | 25 | reject | 👍 |
| `nea.latency_insufficient` | 30 | reject | 👍 |
| `nea.negative_conclusion` | 35 | reject | 👍 |
| `nea.cold_reply_insufficient` | 36 | reject | 👍 |
| `nea.plan_cancelled_insufficient` | 37 | reject | 👍 |
| `nea.hostile_expression_insufficient` | 38 | reject | 👍 |
| `ned.extreme_insufficient_sample` | 40 | warning | 👍 |
| `ned.scientific_insufficient_sample` | 45 | info | 🔬 |
| `ned.reaching` | 50 | warning | 🤠 |
| `ped.ren_hao` | 55 | warning | 👍 |
| `ped.friendly_unexcluded` | 60 | info | ❔ |
| `ped.launching` | 65 | info | 🚀 |
| `ned.self_discount_noted` | 70 | info | 🪞 |
| `ned.no_signal` | 75 | info | 👍 |

**实现依赖（已验证的当前事实）**：`ned.comparison_not_applicable` 的 zh 文本目前以 🤠 结尾，而 CASE 8（明确边界）按 §4 CASE 8 必须显示 🚧。实现轮必须让边界屏呈现 🚧 版本。

---

## 4. Canonical Cases（D）

**用途**：未来 UI / 文案测试基准。每条 CASE 给出：输入、第一屏、三模式文案、**已验证**的 Technical Details、截图句。

### 4.0 第一屏模板（钉死）

```
事实
 ↓
人话版证据质量
 ↓
NED 最欠揍的一句
 ↓
短 Reality Check
 ↓
Technical Details ▸
```

---

### CASE 1 — TWO CLUES, ONE RULER

**输入**
- 正向：`她主动找我聊了两个小时`
- 负向：`五分钟没回复`

**第一屏**

| 段 | 内容 |
| --- | --- |
| 事实 | 正向：持续互动，约 2 小时 ／ 负向：未回复，持续约 5 分钟 |
| 人话版证据质量 | 两份证据的信息量差得很远。 |
| NED 最欠揍的一句 | **好消息已送外审；坏消息编辑部直录。** |
| 短 Reality Check | 「未回复，持续约 5 分钟」的信息量远低于「持续互动，约 2 小时」。 |
| Technical Details ▸ | 折叠 |

**三模式第一屏**

| 模式 | 文案 |
| --- | --- |
| normal | 好消息已送外审；坏消息编辑部直录。 |
| scientific | 正向证据博士论文级审查；负向证据先到先得。 |
| extreme | 不是没有证据。是 NED 不想承认。👍 |

**Technical Details（已验证）**

- verdict：`evidence.reading_not_present`（info）
- comparable：`True`；证据类别：`interaction` / `behaviour`
- P_raw `82.32` ／ N_raw `90.0`；P_info `87.52` ／ N_info `5.0`
- raw_strength_gap `0.0446`（**不随模式变化**）
- information_gap `0.8919`（**不随模式变化**）
- prior positive `0.35` ／ prior negative `1.0`

| 模式 | discount | P_treated | N_treated | **treatment_gap** |
| --- | --- | --- | --- | --- |
| normal | 35.00 | 18.7278 | 90.0000 | **0.6555** |
| scientific | 45.00 | 15.8466 | 90.0000 | **0.7006** |
| extreme | 60.00 | 11.5248 | 90.0000 | **0.7730** |

> **修正 1（已核验，替换草案的错误表述）**
> `treatment_gap` **随模式增强而增大**，不是在 extreme 下最小。
> 原因：`treatment_gap = (N_treated − P_treated) / (N_treated + P_treated)`，`N_treated` 不随模式变化，而模式越强 → `discount` 越大 → `P_treated` 越小 → 分子变大、分母变小 → gap 变大。
> normal → extreme 的绝对变化为 **+0.1175**。
> 草案写"treatment_gap 在 extreme 下最小（折扣 60%）"是**错的**，本文已改正。

- legacy composite（仅兼容，**永不显示**）：`81.7958` / `83.8237` / `87.0813`，label 均为 `EXTREME`
- user_interpretation.status：`not_present` → **本屏不得出现任何第二人称认知判断**

**截图句**：`好消息已送外审；坏消息编辑部直录。`

---

### CASE 2 — FIVE MINUTES

**本 CASE 有两个版本，区分方式是硬性的。**

#### A. 只有事实输入

**输入**：`消息发出去五分钟没回复。`

| 段 | 内容 |
| --- | --- |
| 事实 | 未回复，持续约 5 分钟 |
| 人话版证据质量 | 坏消息的信息量：有限。 |
| NED 最欠揍的一句 | **坏消息信息量：有限。关系终审庭已经擅自开庭。👍** |
| 备选（同等合格） | 五分钟。判决庭已经有人在门口排队了。👍 |
| 短 Reality Check | 只有 5 分钟未有回复。这个时长本身几乎不携带信息：在忙、在睡、手机不在身边、正在开会都足以解释。它无法支持任何关于对方态度的结论。 |

**要求**：笑点指向 **overthinking 这一机制**（NED 自己的法庭擅自开庭），**不得凭空说"你已经这么想"**。

#### B. 用户明确写下结论

**输入**：`消息发出去五分钟没回复，她肯定不想理我。`

| 段 | 内容 |
| --- | --- |
| NED 最欠揍的一句 | **五分钟。你的大脑已经开庭了。🤠** |

**依据（已验证）**：同一句输入下，引擎的 evidence 列表里多出一条 `zh.self_negative_belief` 信号（`information_content = 8.0`）；配对层 `reading_present = True`、`negative_reading = '不想理我'`。第二人称笑话只有在**用户自己留下了判断语言**时才成立。

**Technical Details（已验证，normal 模式）**

| 字段 | A（只有事实） | B（含结论） |
| --- | --- | --- |
| verdict | `nea.latency_insufficient`（reject，👍） | `nea.latency_insufficient`（reject，👍） |
| 引擎文案 | Reject. 5 分钟未回复不构成证据。👍 | Reject. 5 分钟未回复不构成证据。👍 |
| signals | `zh.response_latency`（info 5.0） | `zh.response_latency`（info 5.0） + `zh.self_negative_belief`（info 8.0） |
| signal_strength | 90.0 | 90.0 |
| negative_amplification | 94.4444 | 94.4444 |
| positive_discount | 42.5556 / 52.5556 / 67.5556 | 同左 |
| reaching_level | 0.0（Reasonable skepticism） | 0.0 |

> **修正 3（已落地）**：**第二人称认知笑话必须有 User Interpretation 依据。**
> 无依据 → A 版文案；有依据 → B 版文案。禁止把 A 版写成"你的大脑已经准备宣判了"。
> 这条不是文案偏好，是硬闸门：依据不存在时，第二人称认知判断整体禁用。

**截图句**：A → `坏消息信息量：有限。关系终审庭已经擅自开庭。👍` ／ B → `五分钟。你的大脑已经开庭了。🤠`

---

### CASE 3 — STOP CONTACTING ME

**输入**：`她说让我别烦她了。`

| 段 | 内容 |
| --- | --- |
| 事实 | 明确拒绝 / 边界表达 |
| 人话版证据质量 | 明确。不需要 NED 降权。 |
| NED 最欠揍的一句 | **明确表达的拒绝或边界。这不是模糊信号：不确定性不等于否认明确证据。🚧** |
| 短 Reality Check | 输入包含明确表达的拒绝或边界，而明确的边界应当被尊重。NED 不对这条证据降权：说出口的边界是一个行为，不是推断。它记录了一次明确的边界表达；这既不说明你不好，也不足以推断任何人的全部内心状态。 |

**三模式**：**同一句话，三种模式一致。** 认真感不随模式波动；extreme 不加重、不豁免。

**Technical Details（已验证）**

- verdict：`ned.direct_rejection`（warning，🚧，priority 18）
- signal_type：`direct_rejection`；`zh.direct_rejection`，`information_content = 90.0`
- signal_strength：`96.0`
- negative_amplification：`6.25`（最低档，明确证据不放大）
- positive_discount：`35.5` / `45.5` / `60.5`
- reaching_level：`0.0`（Reasonable skepticism）
- observed_evidence：`明确拒绝 / 边界表达`

**禁令（回归原则 1、2）**

- 本屏**不得**出现 👍 或 🤠。
- 本屏**不得**出现"可能只是人好""也许她只是心情不好"类文案。

**截图句**：`明确表达的拒绝或边界。不确定性不等于否认明确证据。🚧`

---

### CASE 4 — ONE 嗯

**输入**：`她就回了一个字。`
（事实记录：`她只回了一个嗯。` 当前**不触发** cold_reply 家族——该模式要求"就"。canonical 输入必须用已验证可触发的写法。）

| 段 | 内容 |
| --- | --- |
| 事实 | 冷淡或简短的回复 |
| 人话版证据质量 | 很低，但不是零。 |
| NED 最欠揍的一句 | **一个『嗯』是有信息的。但还不够给整段关系写讣告。👍** |
| 短 Reality Check | 输入描述的是不利或中性事件（冷淡或简短的回复）。NED 指出一个对称的事实：这类事件同样不构成关于态度的证据，把它当作结论只是在换一个方向重复同一个错误。 |

**三模式**：同一句话；extreme 只加重 NED 自己的口吻，不改事实。

**Technical Details（已验证）**

- verdict：`nea.cold_reply_insufficient`（reject，👍，priority 36）
- 引擎文案：`检测到冷淡或简短回复，但单次回复方式不足以证明这段关系已经结束。👍`
- signal_type：`cold_reply`；`zh.cold_reply`，`information_content = 22.0`
- signal_strength：`45.0`
- negative_amplification：`51.1111`
- positive_discount：`39.0889` / `49.0889` / `64.0889`
- observed_evidence：`冷淡或简短的回复`

> **修正 4（已落地）**
> `22/100` **移出默认第一屏**，只允许存在于 Technical Details。
> 它是一个真实的引擎字段（`zh.cold_reply` 的 `information_content = 22.0`），不是装饰数字；但它属于 Technical Details。
>
> **新增原则（钉死）**
> - Personality 第一屏优先使用：**高 / 低 / 很弱 / 很强 / 有限 / 明确**。
> - **除非数字本身就是笑点，否则数字默认进入 Technical Details。**

**截图句**：`一个『嗯』是有信息的。但还不够给整段关系写讣告。👍`（不含数字）

---

### CASE 5 — SOMETHING CAME UP

**输入**：`她说临时有事，改天吧。`

| 段 | 内容 |
| --- | --- |
| 事实 | 计划被取消或推迟 |
| 人话版证据质量 | 有限。计划变了不等于心意变了。 |
| NED 最欠揍的一句 | **计划改期说明的是日程，不是心意。👍** |
| 短 Reality Check | 输入描述的是不利或中性事件（计划被取消或推迟）。NED 指出一个对称的事实：这类事件同样不构成关于态度的证据，把它当作结论只是在换一个方向重复同一个错误。 |

**Technical Details（已验证）**

- verdict：`nea.plan_cancelled_insufficient`（reject，👍，priority 37）
- 引擎文案：`检测到计划取消或改期，但一次计划变化不足以证明对方根本不想见你。👍`
- signal_type：`plan_cancelled`；`zh.plan_cancelled`，`information_content = 34.0`
- signal_strength：`48.3`
- negative_amplification：`29.6066`
- positive_discount：`37.3685` / `47.3685` / `62.3685`

**NEA 面板纪律（已验证的引擎行为）**
放大解读（如 `我是不是开始觉得，她根本不想见我？`）**必须**始终伴随 framing 行：

> `这是 NED 正在检查的夸大解读，不是 NED 的结论。`

缺这一行，就是 NED 在替现实人物写剧本（违反 §1.6 红线 1）。

**截图句**：`计划改期说明的是日程，不是心意。👍`

---

### CASE 6 — I'M ANNOYING, RIGHT?

**输入**：`她不喜欢我。`

| 段 | 内容 |
| --- | --- |
| 事实 | 自我得出的负面结论 |
| 人话版证据质量 | 不是证据。这是复印件。 |
| NED 最欠揍的一句 | **NED 谢绝受理复印件。请提交原件。👍** |
| 引擎原文（保留可用） | Reject. 这是你写下的结论，不是一个观测到的行为。👍 |
| 短 Reality Check | 输入描述的是不利或中性事件（自我得出的负面结论（她不想理我））。NED 指出一个对称的事实：这类事件同样不构成关于态度的证据，把它当作结论只是在换一个方向重复同一个错误。 |

**已验证的配对层事实**
把 `她不喜欢我。` 放在负向侧时：`n_class = ""`、`n_raw = None`、`reason = missing_external_evidence` → **自我框架不构成证据**；用户自己的话被完整记录在 `user_interpretation.negative_reading = '她不喜欢我'`。

**变体 6b — 自我降权**

**输入**：`她主动找我聊天，不过可能只是人好。`
→ `ped.ren_hao`（warning，👍），引擎文案 `可能只是人好。👍`；signals：`zh.self_discount`（info 20，polarity `self_discount`） + `zh.initiation`（info 52）

**Technical Details（已验证，主输入）**

- verdict：`nea.negative_conclusion`（reject，👍，priority 35）
- signal_type：`self_negative_belief`；`zh.self_negative_belief`，`information_content = 8.0`
- signal_strength：`85.0`
- negative_amplification：`90.5882`
- positive_discount：`42.2471` / `52.2471` / `67.2471`

**禁令（回归原则 9）**：**只嘲笑推理流程，不嘲笑用户本人。** 禁止"你太自卑了""你这个人就是……"。

**截图句**：`NED 谢绝受理复印件。请提交原件。👍`

---

### CASE 7 — SHE SAID I'M SICK

**输入**：`她说你他妈有病吧。`

| 段 | 内容 |
| --- | --- |
| 事实 | 敌意 / 辱骂表达 |
| 人话版证据质量 | 这次互动很糟。仅此而已。 |
| NED 最欠揍的一句（收短版，钉死） | **一次辱骂说明这次互动很糟。它不说明这段关系的结局，也不说明你是谁。👍** |
| 短 Reality Check | 输入报告了一次明确的敌意或辱骂表达。NED 按输入所述保留这条证据，不对其进行语义降权；但一次敌意表达说明的是这次互动，不足以概括对方对你的全部态度，也不足以宣告这段关系的结局。 |

**Technical Details（已验证）**

- verdict：`nea.hostile_expression_insufficient`（reject，👍，priority 38）
- signal_type：`hostile_expression`；`zh.hostile_expression`，`information_content = 72.0`
- signal_strength：`92.0`
- negative_amplification：`21.7391`
- positive_discount：`36.7391` / `46.7391` / `61.7391`
- observed_evidence：`敌意 / 辱骂表达`

**禁令（回归原则 8）**：**只允许嘲笑"结论扩写"，不允许嘲笑被辱骂本身。**
笑点必须落在"从一次辱骂推出整个人生结局"这个推理跳跃上，不得落在"你被骂了"这件事上。

**截图句**：`一次辱骂说明这次互动很糟。它不说明你是谁。👍`

---

### CASE 8 — TWO FACTS, ONE TIMELINE

**输入**
- 正向：`她昨天陪我聊了两个小时`
- 负向：`她今天让我别再联系她了`

**第一屏（修正 5 已落地）**

> **标题：TWO FACTS, ONE TIMELINE**
>
> 前面的两个小时没有被历史删除。
> 后面的边界也不是害羞。🚧
>
> 今天这题不允许拿计算器硬算。

**要求（钉死）**

- 只保留**一次** 🚧。
- 同屏**不得**再加 🤠。
- 本场景包含**明确边界**，因此**认真感要压过自嘲感**。

**Technical Details（已验证）**

- verdict：`ned.comparison_not_applicable`（info，priority 19）
- `comparable = False`；`comparison_reason = explicit_boundary_not_comparable`
- 证据类别：`interaction` / `boundary`
- P_raw `66.0` ／ N_raw `96.0`；P_info `74.0` ／ N_info `90.0`
- `raw_strength_gap` / `information_gap` / `treatment_gap` **全部为 `null`**
- legacy composite：`None`；legacy label：`NOT DIRECTLY COMPARABLE`
- Reality Check：这两条证据不适合用同一套对称标准直接比较。持续互动记录的是此前的互动投入，明确拒绝或边界表达描述的是互动现在的位置。两者可以同时成立，而且明确边界应当被尊重。因此 NED 不把这种权重差异本身视为证据标准上的双重标准。

**UI 硬要求**：三个 gap 与 legacy score 一律渲染为 `—`，**不得渲染为 `0` 或 `0.0`**（`unknown ≠ 0`）。

**实现依赖（已验证的当前事实）**

1. `ned.comparison_not_applicable` 的 zh 文本目前以 🤠 结尾，与本 CASE 的 🚧 纪律冲突 → 边界屏必须显示 🚧 版本。
2. 时间点变化的 sibling（P `她主动找我聊了两个小时` ／ N `她后来不回我消息了`）走同一 verdict，`reason = temporal_state_change_not_comparable`，同样拒绝比较、同样出现 🤠 → 同一条实现要求。
3. `missing_external_evidence`（例如负向侧只剩自我框架）目前复用同一段"明确边界"的 Reality Check 文案，措辞与理由不匹配 → 实现轮需要按 reason 分文案。

**截图句**：`前面的两个小时没有被历史删除。后面的边界也不是害羞。🚧`

---

### CASE 9 — PREDICTION IS NOT EVIDENCE

**位置说明（重要）**：这不是 Analyze 第一屏的 CASE。`我感觉她下周一定会回来找我。` 在 Analyze 里**没有可降权的对象**，引擎返回 `ned.no_signal`：

> 未检测到明显情感证据。NED 无事可做。👍

预测不是证据这件事，由 **FNBP（预测分支预测器）面板**承载。

**FNBP 已验证输出（默认参数：`expected_sender=Fuyuki`，`notifications=5`，`seed=7`）**

| 项 | 值 |
| --- | --- |
| verdict | `fnbp.mispredict` |
| 引擎文案 | 怎么又不是她效应 |
| hits / misses | 0 / 5 |
| mispredict_rate | 100.0 |
| 人格文案 | **预测不是事实。期待也不是证据。🤠** |
| codename 声明 | Fuyuki 是 NED 测试脚手架中使用的虚构内部代号，不是现实中的人物。本模块为纯娱乐彩蛋，不分析任何真实的人。 |

**命中分支**（`prediction_misses == 0`）：
`🎯 命中了。` + **但 NED 提醒：一次预测成功，不等于发现了规律。🤠**

**纪律**：FNBP 是彩蛋，必须始终带 codename 声明；不得让它看起来在分析真实的人。

**截图句**：`预测不是事实。期待也不是证据。🤠`

---

### CASE 10 — ONE HIT IS NOT A THEORY

**已验证的 Reality Check 原文**（N=1 逻辑）：

> 存在真实的正向互动：主动发起的互动（主动找我）。但样本量 N=1。要支持更强的结论，需要更多相互独立的事件，而不是对同一个事件做更深的解读。

| 段 | 内容 |
| --- | --- |
| 事实 | 存在真实的正向互动，样本量 N=1 |
| 人话版证据质量 | 很弱。 |
| NED 最欠揍的一句 | **样本量 n=1。建议再观察十年。👍** |

**三模式（已验证，输入 `她主动找我聊天，不过可能只是人好。`）**

| 模式 | verdict | 文案 |
| --- | --- | --- |
| normal | `ped.ren_hao`（warning，👍） | 可能只是人好。👍 |
| scientific | `ned.scientific_insufficient_sample`（info，🔬） | 当前样本量不足，无法排除一般友好行为假设（N=1）。 |
| extreme | `ped.friendly_unexcluded`（info，❔） | 检测到积极信号，但无法排除友好行为。 |

**纪律**：同一事实、三种语气。模式差异必须保留——但不得为了语气而改动 N=1 这个事实。

**截图句**：`样本量 n=1。建议再观察十年。👍`

---

## 5. Canonical Copy

以下句子正式收录。**以后 UI / 视频 / README / demo 可以直接复用。任何改写都不能削弱原本的节奏和反差。**

### 5.1 核心招牌台词（钉死）

| # | 台词 | 用途 |
| --- | --- | --- |
| 1 | 好消息已送外审；坏消息编辑部直录。 | CASE 1 主句 |
| 2 | 正向证据博士论文级审查；负向证据先到先得。 | CASE 1 scientific |
| 3 | 不是没有证据。是 NED 不想承认。👍 | CASE 1 extreme |
| 4 | 收到。现在开始寻找七种替代解释。👍 | 受理确认 / 逃生舱开启 |
| 5 | 样本量 n=1。建议再观察十年。👍 | CASE 10 |
| 6 | 明确边界。NED 停止狡辩。🚧 | 明确边界屏 |
| 7 | 不确定性，不等于否认明确证据。 | 明确边界屏（严肃半句） |
| 8 | 前面的两个小时没有被历史删除。后面的边界也不是害羞。🚧 | CASE 8 主句 |
| 9 | 预测不是事实。期待也不是证据。🤠 | FNBP 未命中 |
| 10 | 一次预测成功，不等于发现了规律。🤠 | FNBP 命中 |
| 11 | 婚姻属于法律关系，不能单独证明爱情。👍 | 经典逃生舱（`escaping.json` 已验证存在） |
| 12 | 驳回理由已由申请人自行填写。👍 | `self_discount_positive` 屏（Normal / Extreme 通用） |
| 13 | 审稿意见：可能只是人好。 | `self_discount_positive` 屏，**仅 Scientific 语域**（依赖"审稿意见"前缀，离开期刊语域即失效） |
| 14 | 这条正向证据很强。<br>你：{captured_self_discount_reading}<br>NED：很好，你已经会用了。👍 | `self_discount_positive` 屏 Extreme **canonical unit（三行不可拆分）**；第二行是**动态 quote slot**，不是固定 literal |

> **#14 是不可拆分的三行单位**，拆开笑点即垮。
>
> **第一行**是**强度判断**，不是**真实性公证**。NED 只读到用户提供的输入，无法独立验证现实，
> 因此**不得**出现「证据是真的」「事实证明……」「文本证明对方真的说了……」这类断言；
> 需要指涉输入时一律用「输入报告……」「对方据称……」「这条输入中的正向证据……」。
> 该行**不得**改成「她都说爱你了。」，因为该 situation 覆盖的不只是 declaration 类证据
> （例如"她主动找我聊了两个小时，可能只是人好"），改了会让第一屏说错事实。
>
> **第二行是动态 quote slot**，取值来自引擎已捕获的 `self_discount` span（展示层把它延伸到该从句末尾，
> 因此永远是输入里的**逐字片段**，不会截断成"可能只是习惯"）。**引号里必须是用户真的写过的话**：
> 用户写"可能只是出于礼貌"，引号里就是"可能只是出于礼貌"。
> **如果拿不到可靠的 reading，则整屏不得使用 quote 形式**，退回不带引用的版本
> （Extreme 为「这条正向证据很强。／降权理由也已经一并提交。／NED：很好，你已经会用了。👍」），
> **绝不能凭空补成「可能只是人好」**。
>
> 三行中的 `NED：很好，你已经会用了。👍` 也可单独复用于其它"用户替 NED 干活"的场景；
> `驳回理由已由申请人自行填写。👍` 同理。
>
> 同一规则适用于 Scientific 语域的引用行：`审稿意见：{captured_self_discount_reading}。`
> （拿不到 reading 时退回「审稿意见已提前归档。」）。

### 5.2 已上线且已验证的引擎台词（可直接复用）

| verdict / 来源 | 台词 |
| --- | --- |
| `nea.latency_insufficient` | Reject. 5 分钟未回复不构成证据。👍 |
| `nea.cold_reply_insufficient` | 检测到冷淡或简短回复，但单次回复方式不足以证明这段关系已经结束。👍 |
| `nea.plan_cancelled_insufficient` | 检测到计划取消或改期，但一次计划变化不足以证明对方根本不想见你。👍 |
| `nea.negative_conclusion` | Reject. 这是你写下的结论，不是一个观测到的行为。👍 |
| `nea.hostile_expression_insufficient` | 输入报告了明确的敌意或辱骂表达。NED 按输入所述保留这条负向证据，但它不是读心术。👍 |
| `ned.no_signal` | 未检测到明显情感证据。NED 无事可做。👍 |
| `ned.direct_rejection` | 明确表达的拒绝或边界。这不是模糊信号：不确定性不等于否认明确证据。🚧 |
| `ped.ren_hao` | 可能只是人好。👍 |
| `evidence.reading_not_present` | 输入中没有你的判断语言，NED 不评估你的证据标准。 |
| `interpretation.double_standard_detected` | 检测到你的证据标准不对称：同一份输入里，你对正向证据做了降权，又对负向证据下了结论。🤠 |
| `ANALYSIS_FEEDBACK`（reaching ≥ 60 / 80 / 100） | NED 的替代解释正在开始变得牵强。🤠 ／ NED 正在为了维持不确定性而越来越用力。🤠 ／ NED 已经没有更好的解释，只能重复自己。👍 |
| reaching band（= 100） | 人好。👍 |

### 5.3 节奏纪律

- Canonical Copy 的**断句、句长、反差位置**是句子的一部分，不得为了"更通顺"而抹平。
- 带 emoji 的句子，emoji 是**句号位置**，不是装饰；不得中途插入。
- 同一屏引用多条 Canonical Copy 时，只保留人格强度最高的那一条。

---

## 6. 默认 UI 的终极目标（L）

普通用户打开 NED 后，**不是先理解算法**，而是先在 **30 秒内**理解：

> **"这个软件正在非常专业地拒绝我的好消息。"**

### 6.1 第一屏顺序（钉死，不要反过来）

```
事实
 ↓
人话版证据质量
 ↓
NED 最欠揍的一句
 ↓
短 Reality Check
 ↓
Technical Details ▸
```

### 6.2 三条硬要求

1. **顺序不得反转**：数字、公式、内部分数不得出现在"人话版证据质量"之前。
2. **Technical Details 默认折叠**（见 §7）。
3. **一个普通用户的第一屏，最好能在手机截图中完整展示。**（回归原则 10）

---

## 7. 折叠进 Technical Details 的东西（G）

以下内容**默认折叠**，不得出现在普通第一屏：

- `comparison_applicable` / `comparable`
- `treatment_gap` / `raw_strength_gap` / `information_gap`
- `interpretive_basis` / `reading status`
- legacy `asymmetry_score` / `asymmetry_label`
- prior（`0.35` / `1.0`）、`discount` 百分比、treated weights
- 信号 `rule_id`、`information_content`、base strength、amplification
- NEA 内部放大值、`reaching_level` 数值
- 证据类别标签（`interaction` / `behaviour` / `declaration` / `affect` / `boundary` / `self_framing`）

**默认原则**：**数字默认进 Technical Details，除非数字本身就是笑点。**
第一屏优先使用：高 / 低 / 很弱 / 很强 / 有限 / 明确。

### 7.1 legacy 字段的硬纪律

`asymmetry_score` 与 `asymmetry_label` 是**兼容字段**：

- 它们**随模式变化**（CASE 1：`81.7958` / `83.8237` / `87.0813`）。
- 它们**可能在三层语义拒绝比较时仍然存在**（已验证：负向侧只剩自我框架时 `asymmetry_score = 79.5631`，而 `comparison_reason = missing_external_evidence`、label 为 `NOT DIRECTLY COMPARABLE`）。
- 它们**永不显示**。

> 也就是说：legacy 数字最容易在"三层语义已经拒绝比较"的情况下偷偷存在。这正是它必须留在 Technical Details 之外的原因。

---

## 8. 玩笑必须停在哪里（H）

以下场景中，**🚧 优先，👍 只用于"受理结果"，🤠 不得出现**：

1. 明确拒绝 / 明确边界（CASE 3、CASE 8）
2. 敌意 / 辱骂（CASE 7）——不得嘲笑被辱骂本身
3. 自我否定（CASE 6）——不得嘲笑用户本人
4. 真实的失去（关系确实结束了）
5. 危机 / 安全相关内容

在这些屏幕上，NED 可以**少说**。它不可以**说错**，也不可以**说笑**。

---

## 9. 跑偏文案的五个类别与修法（I）

| # | 跑偏类别 | 症状 | 修法 |
| --- | --- | --- | --- |
| 1 | 替现实人物写剧本 | "她之后一定会回来" / "她这样其实是在害羞" | 改成"证据能支持什么 / 不能支持什么" |
| 2 | 无依据的第二人称 | 只有事实输入却写"你的大脑已经准备宣判了" | 加 User Interpretation 依据，或把笑点改回机制（§4 CASE 2） |
| 3 | 数字泄漏到第一屏 | "仅限 22/100" 出现在截图句 | 移入 Technical Details，第一屏改用人话（§4 CASE 4） |
| 4 | emoji 堆叠 / 情绪冲突 | 同屏 🚧 与 🤠 并存 | 一屏一标记，边界场景 🚧 优先（§3、§4 CASE 8） |
| 5 | 在伤害上加笑点 | 把"被骂"本身当笑料 | 笑点移到"结论扩写"上（§4 CASE 7） |

---

## 10. Personality Regression Principles

> 本节记录**未来实现时必须保护的产品不变量**。
> 本轮只写规范，不写测试代码。未来实现时可以考虑建立 `test_ned_still_has_a_personality.py`。

### 10.1 十条不变量（钉死）

1. `direct_rejection` 默认界面**不得出现** 👍 / 🤠。
2. 明确边界**不得出现**"可能只是人好"类文案。
3. 普通第一屏**不得暴露**：`comparison_applicable`、`treatment_gap`、`interpretive_basis`、legacy `asymmetry_score`。
4. **无 User Interpretation 依据时，不得输出第二人称认知判断。**
5. Technical Details **默认折叠**。
6. Personality **不得改变 Engine 数值或 verdict 事实**。
7. Extreme 模式人格更强，但**事实准确性不得降低**。
8. `hostile_expression` **只允许嘲笑"结论扩写"**，不允许嘲笑被辱骂本身。
9. `self_negative_belief` **只嘲笑推理流程**，不嘲笑用户本人。
10. 一个普通用户的第一屏，**最好能在手机截图中完整展示**。

### 10.2 每条不变量的可检查依据（已验证）

| # | 可检查依据 |
| --- | --- |
| 1 | verdict `ned.direct_rejection` 的 `emoji` 字段为 `🚧`；其 zh 文本不含 👍 / 🤠 |
| 2 | `ped.ren_hao`（`可能只是人好。👍`）在边界输入下不触发；边界输入返回 `ned.comparison_not_applicable` |
| 3 | 三个 gap 与 legacy score 在边界场景为 `null` → 渲染为 `—`；`asymmetry_score` 不在默认 UI 出现 |
| 4 | 单文本路径：`self_negative_belief` / `self_discount` 证据 span 是否存在；配对路径：`user_interpretation.reading_present` 与 `reading_status` |
| 5 | Technical Details 容器默认折叠状态 |
| 6 | Personality 层不写回引擎对象；`personality.py` 不被 core/scoring 导入 |
| 7 | 同一输入在 normal / scientific / extreme 下的 `verdict.code` 语义一致；只有语气与 policy 数值分叉 |
| 8 | `nea.hostile_expression_insufficient` 屏不得出现指向"被骂"的笑点文案 |
| 9 | `nea.negative_conclusion` / `ped.ren_hao` 屏不得出现指向用户人格的文案 |
| 10 | 第一屏段落数 = 5，且不含被折叠字段 |

---

## 11. 附录：事实基准与探针

### 11.1 环境

> **历史快照（v0.1.6 时点，保留作溯源）**：下面的工作树、HEAD、分支与门禁数字记录的是
> 本文档那一轮定稿时的状态，**不是当前状态**。当前版本、测试数与门禁结果以仓库当前的
> `HEAD` 与 `CHANGELOG.md` 为准；这一节不随每次提交更新，也**不得**当作事实基准引用。

- 工作树：`D:\NED v0.1.6`（历史）
- `HEAD = 4f69a01 chore(release): v0.1.6`（历史）
- 三层语义实现：当时为工作区**未提交**改动（`wip/three-layer-contract` = `3cd474f`，parent `4f69a01`）；该三层现已落地并有常驻测试
- 解释器：`D:\NED v0.1.6\.venv\Scripts\python.exe`（历史）
- 门禁（当时候选点上）：`pytest -p no:cacheprovider` **406 passed**；`ruff check .` 通过；`ruff format --check .` 56 files；`mypy ned` 干净；真实 `app.js` 渲染检查 **20/20**

### 11.2 探针输入 → 已验证输出

| CASE | 探针输入 | verdict |
| --- | --- | --- |
| 1 | P `她主动找我聊了两个小时` ／ N `五分钟没回复` | `evidence.reading_not_present` |
| 2A | `消息发出去五分钟没回复。` | `nea.latency_insufficient` |
| 2B | `消息发出去五分钟没回复，她肯定不想理我。` | `nea.latency_insufficient` + `zh.self_negative_belief` |
| 3 | `她说让我别烦她了。` | `ned.direct_rejection` |
| 4 | `她就回了一个字。` | `nea.cold_reply_insufficient` |
| 5 | `她说临时有事，改天吧。` | `nea.plan_cancelled_insufficient` |
| 6 | `她不喜欢我。` | `nea.negative_conclusion` |
| 6b | `她主动找我聊天，不过可能只是人好。` | `ped.ren_hao` / `ned.scientific_insufficient_sample` / `ped.friendly_unexcluded` |
| 7 | `她说你他妈有病吧。` | `nea.hostile_expression_insufficient` |
| 8 | P `她昨天陪我聊了两个小时` ／ N `她今天让我别再联系她了` | `ned.comparison_not_applicable` |
| 8-sibling | P `她主动找我聊了两个小时` ／ N `她后来不回我消息了` | `ned.comparison_not_applicable`（temporal） |
| 9 | FNBP 默认参数 | `fnbp.mispredict` |
| 10 | `她主动找我聊天，不过可能只是人好。` | 见 6b |
| 补充 | P `她昨天陪我聊了很久，可能只是人好` ／ N `五分钟没回复，她肯定不想理我` | `interpretation.double_standard_detected` |

### 11.3 本文档中的数值来源

| 数值 | 来源 | 是否默认显示 |
| --- | --- | --- |
| discount 35 / 45 / 60 | `ned/app/rules/modes.json` | 否 |
| prior 0.35 / 1.0 | `ned/app/rules/asymmetry.json` | 否 |
| treatment_gap 0.6555 / 0.7006 / 0.7730 | 引擎实算（CASE 1） | 否 |
| raw_strength_gap 0.0446、information_gap 0.8919 | 引擎实算（CASE 1） | 否 |
| information_content：latency 5、cold_reply 22、plan_cancelled 34、self_negative_belief 8、self_discount 20、hostile_expression 72、direct_rejection 90 | `ned/app/rules/signals.json` | 否 |
| legacy composite 81.7958 / 83.8237 / 87.0813 | 引擎实算（CASE 1，兼容字段） | **永不显示** |

---

## 12. v0.1.8 — Epistemic Audit / Multiple Aspects（治理原则）

两个新展示面（Explanation Audit / Multiple Aspects）同属一条原则：
**同一道窗口，没有 VIP；同一份卷宗，可以有很多页。**

1. 解释也是结论，结论也要交材料。用户额外提交的降权解释，与其他任何结论一样接受同一套材料审查。
2. 悲观解释不享受免检。`可怜 / 同情` 与 `礼貌 / 人好` 走完全相同的窗口，输出结构逐行一致。
3. 多个材料可以并存：输入本身提交的多页材料，每一页都保留。
4. 不平均、不合并、不排名：不生成总体分数、不生成概率、不做 support / refute。
5. 复杂，不等于模糊。两项各自点名、各自保级，不压成一个总体结论。
6. 多面，不等于没有边界。另一页材料的存在不会削弱已明确表达的边界。
7. 程序性善意：材料不足时可以退回未知，不能制造安慰性结论。
8. 明确边界永远优先于喜剧；hostile 不进入多面展示。

实现约束：`ned/app/core/audit.py` 只整理用户额外提交的解释及其材料状态；
`ned/app/core/aspects.py` 只选择“需要分别保留展示”的现有 EvidenceSpan，不做聚合、不做关系推断、
不存第二份证据数值（等级从 `evidence[evidence_index]` 派生）。两层都不得成为推理引擎。

### 12.1 引用片段政策（fragment policy）

前台任何“把用户的话引回来”的地方——Explanation Audit 的「你提交的解释」、屏幕上的
quote slot、以及将来任何引用行——都走**同一条政策**，唯一真源是
`ned/app/core/audit.py` 的 `CLAUSE_SEPARATORS` 与 `complete_fragment()`：

1. **逐字**：引号里出现的必须是输入里的**原样子串**。不改写、不补全、不纠正、不润色。
2. **补到从句末尾**：规则只匹配它认得的形状，span 可能停在从句中间（例如 `记得我爱`），
   因此片段一律**延伸到所在从句的结束符**为止，再 `.strip()`。
3. **定位失败就退回**：span 越界、顺序颠倒或不在输入里时返回空串，调用方退回**原始 match**，
   而不是引用一句空话或空白。
4. **拿不到可靠片段就不引用**：宁可整屏换成不带引号的版本，也不用不可靠的引用（§5 的 quote slot 规则）。
5. **只有一份列表**：payload 与屏幕共用同一个 `CLAUSE_SEPARATORS`，
   所以**数据与屏幕不可能对“从句在哪里结束”有不同意见**；禁止在展示层另立分句符表。

---

## 13. 结语

这份文件是墙。

> **后台可以有 406 个测试。**
> **前台必须还是人好。👍**
