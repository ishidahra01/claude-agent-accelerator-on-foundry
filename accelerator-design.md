# Azure Well-Architected Review Agent Accelerator on Foundry — リポジトリ拡張 設計ドキュメント

> 既存リポジトリ `ishidahra01/claude-agent-accelerator-on-foundry`（Claude Agent SDK 製の Azure リソース分析エージェントを Foundry Hosted Agent で動かす土台）を、
> **Build → Host → Observe → Evaluate → Control → Optimize → ROI** の本番ライフサイクル全体に拡張するための設計図。
> コードは実装者（ご自身）が書く前提で、本書は **構造・責務・インターフェース・スキーマ・段階計画** のみを定義する。
>
> 構成は2つの Deep Dive に分かれ、**どちらか一方だけでも単体コンテンツ（教材／デモ／ピッチ）として成立する**ように設計している。
> - **Part A — Harness Deep Dive**：Claude Agent SDK × Microsoft Agent Framework × Foundry Hosted Agent（「作って載せる」の技術深掘り）
> - **Part B — Trust→ROI Deep Dive**：Observe / Evaluate / Control / Optimize / ROI（「運用して価値を証明する」の深掘り）

最終更新: 2026-06-03 / 対象: Microsoft Build 2026 時点の Foundry 機能

---

## 0. このドキュメントの位置づけとゴール

### 0.1 何を達成する拡張か
既存リポジトリは「Claude Agent SDK の良さ（SubAgent / Skills / built-in tools / context管理 / MCP）を Foundry Hosted Agent に載せる」ところまでを射程にしている。本拡張のゴールは次の3点。

1. **Harness を見せ切る**：Claude Agent SDK の agent loop・context管理・SubAgent境界・Hooks を、コードと観測の両面から「中で何が起きているか」分かる状態にする。
2. **運用ループを閉じる**：Observe（トレース）→ Evaluate（ASSERT/Rubric）→ Control（ACS）→ Optimize → ROI を1リポジトリで通す。
3. **そのままデモになる**：悪いAzure構成サンプルを入れると指摘が出て、トレース・評価・ROIまで一気通貫で見せられる。

### 0.2 Build 2026 の3メッセージとの対応（章の背骨）
| メッセージ | 対応する本書のPart | Buildセッション |
|---|---|---|
| どのフレームワークでも本番運用できる（framework flexibility） | Part A | BRK243 / LAB540 |
| どのフレームワークでも信頼できる（trust across any framework） | Part B（Eval / Control） | BRK250 |
| 観測からROIまで閉じる（observability → ROI） | Part B（Observe / Optimize / ROI） | BRK252 |

### 0.3 機能ステータス凡例（SEが「今どこまで本物か」を語るための注記）
本書で参照する Foundry 機能のステータス（Build 2026 時点）。設計判断とトーク両方で使う。

| 機能 | ステータス |
|---|---|
| Microsoft Agent Framework（agent harness: skills/memory/middleware） | Stable |
| MAF ↔ Claude Agent SDK 連携 / GitHub Copilot SDK 連携 | Stable |
| Multi-agent orchestration（Magentic-One 含む） | Stable |
| `agent-framework-claude`（`ClaudeAgent`） | Public preview（`--pre`） |
| Agent Framework Harness（shell / filesystem / approval / compaction） | Stable |
| Hosted Agents（sandbox / state / filesystem persistence / framework-agnostic） | GA見込み 2026年7月初旬 |
| Hosted Agents Identity（Entra Agent ID / Managed Identity / OBO） | Public preview〜GA範囲 |
| Hosted Agents scale-to-zero / managed endpoint | GA見込み 2026年7月初旬 |
| Hosted Agents built-in guardrails（Content Safety） | Public preview |
| Routines（定期・スケジュール実行） | Public preview |
| 任意フレームワークの Tracing / Evaluations | Public preview（一部 GA） |
| ASSERT（ポリシー駆動評価） | オープンソース |
| Agent Control Specification（ACS） | オープンソース標準 |
| Rubric evaluator | Public preview |
| Guided Guardrail Setup | Public preview |
| Multi-turn eval / User Simulation / Intelligent sampling / Traces-to-dataset / Trace replay | Public preview |
| Runtime DLP（Purview）/ Purview insights in Control Plane | Public preview / GA |
| Agent Optimizer | Private preview |
| Agent ROI | Private preview |
| Memory（procedural / user / session） | Public preview（procedural は Tau-bench で +7〜14%） |

---

## 1. 拡張後の全体アーキテクチャ

```
                ┌──────────────────────────────────────────────────────────────┐
               User/Client →│                 Microsoft Foundry Hosted Agent                │
               (Responses   │   Managed harness layer                                       │
                API /       │   - isolated sandbox / persistent filesystem / state          │
                Invocations)│   - Entra Agent ID / Managed Identity / OBO                   │
                │   - managed endpoint / scale-to-zero / built-in guardrails    │
                │   - OTel traces / metrics / App Insights integration          │
                │   ┌──────────────────────────────────────────────────────┐   │
                │   │  server.py  (runtime adapter / entry)                 │   │
                │   │   - Responses API or Invocations 受け                  │   │
                │   │   - session/state/filesystem/identity 橋渡し            │   │
                │   │   - approval / guardrail / observability 接続点         │   │
                │   └──────────────────────┬───────────────────────────────┘   │
                │                          │ query()                            │
                │   ┌──────────────────────▼───────────────────────────────┐   │
                │   │   Claude Agent SDK Main Agent                         │   │
                │   │   plans & delegates                                   │   │
                │   │     ├─ Explore Agent      (SubAgent)                  │   │
                │   │     ├─ Security Analyzer   (SubAgent)                  │   │
                │   │     └─ Cost Optimizer      (SubAgent)                  │   │
                │   │   Skills: Azure WAF (progressive load)                 │   │
                │   │   Built-in tools: Read/Write/Edit/Bash/Glob/Grep       │   │
                │   │   MCP: MS Learn Docs (future)                          │   │
                │   │   Hooks ──────────────► tracing/eval/approval          │   │
                │   └──────────────────────┬───────────────────────────────┘   │
                │                          │ model calls                        │
                │   ┌──────────────────────▼───────────────────────────────┐   │
                │   │  Claude model deployment on Foundry                    │   │
                │   │  (CLAUDE_CODE_USE_FOUNDRY=1)                           │   │
                │   └───────────────────────────────────────────────────────┘   │
                └──────────────────────────────────────────────────────────────┘
                  │ traces / evals / metrics / guardrail events
                  ▼
               Foundry AI Operations: Tracing → Evaluations(ASSERT/Rubric) → Optimizer → Agent ROI
                  + ACS guardrails (5 checkpoints) + Content Safety + Azure Monitor / Purview DLP
```

**設計上の不変条件（変えない境界）**
- `backend/` の中に Python ソース・`.claude/` 定義・`.foundry/` メタデータを同梱（Hosted Agent として載せやすくするため）。frontend/docs/example は後付けでもこの境界を壊さない。
- 観測・評価・制御は **Hooks と ACS という"横断レイヤー"** に寄せ、エージェント本体のロジックに混ぜない。
- Harness は **Claude Agent SDK の内側の harness（agent loop / SubAgent / Skills / tools）** と、**Foundry Hosted Agent の外側の managed harness（sandbox / state / identity / scale / guardrails / observability）** の二層として扱う。どちらかに寄せ切らず、Claude SDK の強みを残したまま Hosted Agent のマネージド機能を使う。

---

## 2. 拡張後のリポジトリ構造（設計目標ツリー）

既存ロードマップのツリーを土台に、Part A/B で必要なファイルを追記（★=本拡張で新規／拡充）。

```
backend/
  src/
    agent/
      main_agent.py              # Main Agent: 計画と委譲。query() 実行フロー
      subagents/                 ★ SubAgent をコードからも参照する場合の薄いラッパ
        explore.py               ★ （定義は .claude/agents に置き、ここは登録/メタのみ）
        security_analyzer.py     ★
        cost_optimizer.py        ★
      skills/
        azure_waf.py             # WAF Skill のローダ/補助
      observability/
        tracing.py               ★ Hooks → トレース（OTel/Azure Monitor）へ
        evaluation.py            ★ ASSERT/Rubric 実行・スコア集約
        roi.py                   ★ ROI 指標（完了率・削減時間・コスト効率）算出
      control/                   ★ ACS 制御の適用点
        acs_runtime.py           ★ 5チェックポイントに guardrail を差し込む
      server.py                  # Hosted Agent エントリ（Responses/Invocations 受け）
  .claude/
    CLAUDE.md                    # Main Agent のシステム規範
    agents/
      explore-agent.md
      security-analyzer.md
      cost-optimizer.md
    skills/
      azure-well-architected/
        SKILL.md                 # WAF 5本柱の段階ロード用ナレッジ
  evals/                         ★ 評価アセット（コードと分離）
    policies/                    ★ ASSERT 用ポリシー（YAML）
      security.policy.yaml       ★
      cost.policy.yaml           ★
      waf.policy.yaml            ★
    rubrics/                     ★ Rubric 定義（重み付き品質基準）
      analysis-quality.rubric.yaml ★
    scenarios/                   ★ User Simulation / multi-turn シナリオ
  control/                       ★ ACS 制御契約
    acs.policy.yaml              ★ input/LLM/state/tool/output の制御
  .foundry/
    agent-metadata.yaml          # Foundry Hosted Agent メタデータ
  infra/                         ★ azd デプロイ（bicep/azd）
  pyproject.toml
example/                         ★ サンプル入力（悪い構成を含む）
  good-config/                   ★ 指摘が少ない健全な構成
  bad-config/                    ★ 指摘が必ず出る構成（デモの主役）
docs/
  deploy-hosted-agent.md         # azd デプロイ手順
  harness-deepdive.md            ★ Part A の読み物（単体成立）
  trust-roi-deepdive.md          ★ Part B の読み物（単体成立）
frontend/                        # 後付け
```

> ポイント：**評価・制御アセット（`evals/`・`control/`）をコードから分離**して YAML 化することが、ASSERT/ACS/Rubric の「ポータブル・監査可能」というMSメッセージと直結する。実装者はコードを書くが、ポリシーはレビュー対象の成果物として独立させる。

---

# Part A — Harness Deep Dive
## Claude Agent SDK × Microsoft Agent Framework × Foundry Hosted Agent

> **このPartの主張**：Claude Agent SDK は「もう一つのオーケストレーションFW」ではなく、Claude Code を支える**実証済みの agent runtime**。その agent loop・context管理・SubAgent境界を捨てずに、Foundry Hosted Agent の managed harness（sandbox / state / filesystem persistence / identity / scale / observability / guardrails）に載せられる——これが "any harness, any framework" の具体。

### A0. Harness の二層モデル（Claude SDK harness × Hosted Agent managed harness）

**Harness = Agent が「考える」モデル推論を、実作業環境・ツール実行・状態管理・安全制御につなぐ実行レイヤー**と定義する。本リポでは Harness を1つの製品機能ではなく、以下の二層として扱う。

| 層 | 主役 | 何を担当するか | 本リポでの見せ方 |
|---|---|---|---|
| **Inner harness** | Claude Agent SDK（必要に応じて MAF の `ClaudeAgent`） | agent loop、SubAgent委譲、Skills、built-in tools、MCP、Hooks、SDK session、context compaction | Azure構成を読み、Explore/Security/Cost に分担し、構造化レポートを作る「思考と作業の中身」を見せる |
| **Outer managed harness** | Foundry Hosted Agent | sandbox、filesystem persistence、session/state、managed endpoint、scale-to-zero、Entra Agent ID / Managed Identity / OBO、Content Safety guardrails、OTel/App Insights、承認・統制の接続点 | 同じ Claude SDK agent を企業向けにホストし、隔離・ID・永続化・監視・スケールを Foundry に任せる |

**設計判断**
- Claude Agent SDK の良さ（自律ループ、SubAgent境界、Skills、built-in tools、Hooks）は **内側に残す**。Hosted Agent に載せるために SDK の実行モデルを薄めない。
- Hosted Agent の良さ（sandbox、永続FS、identity、scale、guardrails、observability）は **外側で使う**。アプリコードで VM 管理・状態保存・ID配布・監視基盤を作らない。
- MAF は「Claude SDK を企業標準の agent abstraction / workflow に接続する bridge」として扱う。MAF が内側の harness を置き換えるのではなく、Hosted Agent に載せやすい形へ包む役割を持たせる。

**Part A のデモ観点**
1. ローカル/開発時：Claude Agent SDK の `query()` と SubAgent/Skills で、agent loop の中身を見せる。
2. Hosted Agent 化：同じ agent を専用 sandbox と永続FSで実行し、セッションを跨いだ作業ディレクトリ・状態継続を見せる。
3. 企業運用化：Managed Identity/OBO、approval checkpoint、built-in guardrails、OTel/App Insights の run step 可視化を見せる。
4. 発展形：`agent-framework-claude` で MAF workflow に組み込み、「Claude SDK harness を他の agent と混在できる部品」として示す。

### A1. Claude Agent SDK の「見せどころ」9点と設計反映

各機能を「デモで何を見せるか」「設計でどこに効かせるか」で定義する。

| # | SDK機能 | 何を見せるか | 設計への反映（どのファイル/定義） |
|---|---|---|---|
| 1 | **Autonomous agent loop**（`query()`） | アプリ側でtool-useループを書かない。SDKが計画→tool選択→実行→反復を駆動 | `main_agent.py` は `query()` 呼び出しに専念。委譲判断はプロンプト/定義側 |
| 2 | **SubAgent（context isolation）** | Explore/Security/Cost が別contextで深掘りし、要約だけ親に返す | `.claude/agents/*.md` で定義。`subagents/*.py` は登録の薄皮のみ |
| 3 | **Built-in tools** | Read/Write/Edit/Bash/Glob/Grep/WebSearch/WebFetch を実装ゼロで利用 | Explore は Read/Glob/Grep で大きなJSONを走査→要点抽出 |
| 4 | **Progressive context loading（Skills）** | WAF 5本柱を「必要時だけ」ロード（system promptを膨らませない） | `.claude/skills/azure-well-architected/SKILL.md` |
| 5 | **MCP native** | 外部知識/ツールを標準接続。将来 MS Learn Docs MCP | MCP接続点を `main_agent.py` の options に集約 |
| 6 | **Hooks（lifecycle）** | tool呼び出し・SubAgent遷移・message turn を横断観測 | **Part B の tracing/eval の唯一の注入点**（A↔B の接合部） |
| 7 | **Permissions（`allowed_tools`）** | SubAgentごとに使えるtoolを最小化＝blast radius縮小 | 各 SubAgent 定義に許可toolを宣言。企業運用の安全性訴求 |
| 8 | **Sessions** | 複数リクエストを同一会話として継続（Hosted Agent でstate保持） | `server.py` がFoundryのstateとSDK sessionを対応付け |
| 9 | **Large context / 自動compaction** | 大きなAzureエクスポートでも親contextを破綻させない | SubAgent + compaction の合わせ技。truncation自前実装が不要 |

**差別化トーク（単体コンテンツ用の決め台詞）**
> 「LangGraph/AutoGen は state遷移・graph orchestration が強い。Claude Agent SDK は **長い入力・大きなtool出力・SubAgent境界・必要時ロードのドメイン知識** という"contextの運用問題"に最適化された runtime。だから自前ループ・自前truncation・自前tool handler を書かずに本番品質に届く。」

### A1.5 Hosted Agent managed harness の「見せどころ」10点と設計反映

Claude Agent SDK が内側の agent runtime を担当する一方で、Hosted Agent は本番運用に必要な外側の実行基盤を担う。Part A ではここを **Claude SDK を企業運用に載せるための managed harness** として深掘りする。

| # | Hosted Agent / MAF Harness機能 | 何を見せるか | 設計への反映（どのファイル/定義） |
|---|---|---|---|
| 1 | **Hosted shell / filesystem** | Agent が管理環境上の作業ディレクトリで Read/Write/Edit/Bash を実行する | `server.py` が入力を sandbox FS に展開し、SDK built-in tools の作業領域として渡す |
| 2 | **Filesystem persistence** | scale-to-zero や複数ターン後も中間成果物・分析レポートを保持できる | `server.py` が session ID ごとの workspace path を決め、成果物を `/work/<session>/` 相当に保存 |
| 3 | **Session state** | Responses API の会話 state と Claude SDK session を対応付ける | `server.py` の state adapter。SDK session ID / Foundry thread/run ID / filesystem path を束ねる |
| 4 | **Isolation / sandbox** | セッション間でファイル・資格情報・状態が混ざらない | `.foundry/agent-metadata.yaml` に isolation 前提、`infra/` に実行環境・ネットワーク境界を記述 |
| 5 | **Identity** | APIキーではなく Entra Agent ID / Managed Identity / OBO で Azure Resource Graph 等にアクセスする | `infra/` で managed identity と RBAC、`server.py` で token acquisition、`.foundry/agent-metadata.yaml` で必要スコープを宣言 |
| 6 | **Approval checkpoint** | Bash/Write/外部アクセスなどの前に明示承認を挟める | Claude SDK Hooks または MAF middleware から `control/acs_runtime.py` に接続し、危険操作を allow/block/approve に分岐 |
| 7 | **Managed endpoint / scale-to-zero** | 自前サーバ運用なしで endpoint 化し、アイドル時はコストを落とす | `infra/` と `.foundry/agent-metadata.yaml` に endpoint、concurrency、scale 設定を持たせる |
| 8 | **Built-in guardrails** | Content Safety ベースの入出力チェックを runtime 側で実施する | Hosted Agent guardrails を first line、ACS を deterministic policy layer として重ねる |
| 9 | **Observability** | session / tool call / run step を OTel/App Insights/Foundry trace で可視化する | Claude SDK Hooks → `observability/tracing.py` → Hosted Agent/Foundry AI Operations に集約 |
| 10 | **Context compaction** | 長時間セッションの履歴肥大を managed harness / SDK harness の両面で扱う | Claude SDK compaction を内側、MAF/Hosted Agent の履歴管理を外側として役割分担 |

**責務分担の原則**
- **ツールをどう選ぶか、どのSubAgentへ任せるか、どう要約するか**は Claude Agent SDK 側に置く。
- **どこで実行するか、どのIDでアクセスするか、状態をどこに残すか、どのイベントを監視へ送るか**は Hosted Agent 側に置く。
- **危険操作の判断**は三層で重ねる：SDKの `allowed_tools` → Hosted Agent / MAF の approval checkpoint → ACS の deterministic control。

### A2. Microsoft Agent Framework（MAF）統合の設計

**なぜ MAF を噛ませるか**（SDK単体でも動くのに、敢えて挟む理由）
- `BaseAgent` という共通抽象で **プロバイダ差し替え/混在** が可能（Claude ↔ Azure OpenAI ↔ GitHub Copilot SDK）。
- **multi-agent workflow**（sequential / concurrent / handoff / group-chat、Magentic-One）に Claude を1部品として組み込める。
- declarative agent定義・A2A・sessions/streaming の標準パターンに乗る。
- Agent Framework Harness の shell / filesystem / approval / compaction と接続し、Hosted Agent の managed harness へ移しやすい形にできる。

**設計判断（2段構え）**
- **既定構成**：Claude Agent SDK を直接ホストし、SDKの agent loop をそのまま見せる（Harness の純度が高い＝Part Aの主役）。
- **Hosted Agent 構成**：Claude SDK を `server.py` から呼び出し、Hosted Agent の sandbox / persistent FS / state / identity / observability を外側で使う（本番運用の主役）。
- **拡張構成**：`agent-framework-claude` の `ClaudeAgent`（`BaseAgent`）でラップし、MAF の workflow や approval middleware に組み込む例を1本用意（「Claude が Azure OpenAI の出力をレビューする」等のマルチエージェント）。デモ幕間の"発展形"として提示。

```
# 依存（設計メモ・実装はご自身で）
pip install agent-framework-claude --pre   # MAF の Claude 連携（preview）
pip install claude-agent-sdk               # 低レベル制御/ローカルテスト用
```

**設計インターフェース（責務だけ定義）**
- `ClaudeAgent(instructions=..., tools=[...])` を `async with` で扱い、`run()` / `run_stream()` を MAF 側の呼び出し規約に合わせる。
- MAF workflow に載せる際は、SubAgent群を「Claudeエージェント内部の委譲」として閉じ、MAF からは1ノードに見せる（多重オーケストレーションの混乱を避ける）。
- approval / shell / filesystem は **MAF Harness の機能を使える場合は使う**。ただし Claude SDK built-in tools と二重定義しないよう、`server.py` が「Hosted Agent FSをSDKの作業ディレクトリに渡す」「危険操作はHooks/middlewareでapprovalへ流す」という境界を持つ。

### A3. Foundry Hosted Agent への載せ方（runtime adapter 設計）

**2プロトコルの選択指針**
| プロトコル | 使う場面 | 本リポでの既定 |
|---|---|---|
| **Responses API** | OpenAI互換のステートフル対話。標準的なエージェント呼び出し | デモ/標準対話はこちら |
| **Invocations protocol** | スキーマ自由・pass-through。req/resp形式を自分で握る | 「Azureエクスポート投入→構造化JSON返却」のバッチ的呼び出しに好適 |

**`server.py`（runtime adapter）の責務（実装はご自身、ここは仕様）**
1. Foundry の呼び出し（Responses/Invocations）を受け、入力（Azure構成JSON/ARM）を作業ディレクトリへ展開。
2. Claude Agent SDK の `query()` を起動し、Hooks をトレース/評価へ配線（Part B）。
3. **session ↔ Foundry state** の対応付け（会話継続）。
4. **filesystem**：Hosted Agent のサンドボックスFSを SDK の Read/Write/Edit の作業領域として使う（中間成果物・分析出力）。
5. **identity**：Managed Identity / Entra Agent ID / OBO で Azure Resource Graph・Storage・Monitor 等へアクセスし、ローカルAPIキー依存を本番では避ける。
6. **approval checkpoint**：Bash/Write/外部到達などの前に、Claude SDK Hooks / MAF middleware / ACS runtime のいずれかを通して allow/block/approve を判断する。
7. **guardrails**：Hosted Agent の Content Safety guardrails を入出力の first line として使い、ACS の schema/policy control と重ねる。
8. **observability**：Hosted Agent の run/session/tool-call イベントと Claude SDK Hooks を同じ trace に寄せ、Foundry AI Operations / Azure Monitor / App Insights で見えるようにする。
9. 出力を期待スキーマ（下記）に整形して返す。

**期待する出力スキーマ（契約として固定）**
```json
{
  "summary":  { "resourcesAnalyzed": 25, "securityFindings": 12, "costSavingsOpportunities": 8 },
  "security": [ { "severity": "Critical", "resource": "...", "finding": "...", "remediation": "..." } ],
  "cost":     [ { "resource": "...", "recommendation": "...", "estimatedSavings": "$15/month" } ],
  "architecture": [ { "pillar": "Operational Excellence", "finding": "...", "recommendation": "..." } ]
}
```
> この固定スキーマが **評価（ASSERT/Rubric）と ROI 計測の入力**になる（Part B が依存）。スキーマを先に決めるのが拡張の最重要設計判断。

**設定・認証（設計メモ）**
```
CLAUDE_CODE_USE_FOUNDRY=1
ANTHROPIC_FOUNDRY_API_KEY=...        # APIキー方式
ANTHROPIC_FOUNDRY_RESOURCE=...
ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-4-5
```
- 企業運用版では **Entra ID / Managed Identity** に切替（キーレス）。`.foundry/agent-metadata.yaml` と `infra/`（azd）で表現。
- 対話型利用では **OBO（on-behalf-of）** でユーザー文脈を伝搬し、サブスクリプション/リソースグループ単位の権限境界を保持する。
- **Routines（preview）** を使えば「毎晩サブスクリプションをスキャンしてレポート」を定期実行として設計可能（夜間トリアージのデモ価値）。

**`.foundry/agent-metadata.yaml`（設計項目）**
- agent名/バージョン、対応プロトコル、必要環境変数、エントリポイント、必要権限スコープ、managed identity、OBO可否、sandbox/FS persistence、scale-to-zero、approval要否、built-in guardrails、観測の有効化フラグ。

**Hosted Agent Harness Deep Dive の見せ方**
- **Filesystem persistence**：1ターン目で Azure export を展開・正規化し、2ターン目で「前回の分析結果との差分」を同じ作業ディレクトリから読む。
- **Identity**：APIキー実行と Managed Identity/OBO 実行を比較し、「どのAzureリソースへ、誰の文脈でアクセスしているか」を trace 属性に出す。
- **Approval**：Bash や Write の前に approval checkpoint が入り、許可後だけ成果物を書き出す様子を見せる。
- **Scale-to-zero / managed endpoint**：アプリ側の常駐プロセスを持たずに endpoint として呼べること、再開後も session filesystem が残ることを示す。
- **Observability**：Hosted Agent の run step と Claude SDK の SubAgent/tool span を1つの trace tree として表示する。
- **Guardrails**：Content Safety guardrails（runtime）と ACS（policy contract）の二段構えを、同じ入力に対する before/after で示す。

### A4. Part A 単体コンテンツの「読み筋」（docs/harness-deepdive.md）
1. 課題：自前 agent ループ/context管理/実行環境運用の限界 → 2. Harness の二層モデル（Claude SDK inner harness × Hosted Agent managed harness） → 3. Claude SDK 9機能ツアー（A1） → 4. Hosted Agent managed harness 10機能ツアー（A1.5） → 5. MAFで部品化・approval/workflow接続（A2） → 6. Hosted Agent に載せる（A3） → 7. デモ：悪い構成→SubAgent委譲→sandbox FS永続化→approval→trace→構造化レポート。
> これだけで「フレームワーク選定 × 企業ホスティング」の技術セッション1本になる。

---

# Part B — Trust→ROI Deep Dive
## Observe / Evaluate / Control / Optimize / ROI

> **このPartの主張**：エージェントは出荷が始まり。**見える→評価できる→制御できる→改善できる→価値を金額/時間で示せる**まで閉じて初めて本番。ASSERT/ACS は **OSS・任意フレームワーク・ポータブル**で、Foundry の Optimizer/ROI が運用ループを回す。

### B1. Observe — Hooks をトレースに（observability/tracing.py 設計）

**設計方針**：Claude Agent SDK の **Hooks を唯一の観測注入点**にし、エージェント本体にトレースコードを散らさない（横断的関心事として分離）。

**`tracing.py` の責務**
- Hooks イベント（tool呼び出し開始/終了、SubAgent 遷移、message turn、エラー）を **スパン**に変換。
- OpenTelemetry 互換で出力し、**Azure Monitor / Foundry のトレース**に集約。
- スパン属性に最低限：`subagent名`・`tool名`・`入出力サイズ`・`所要時間`・`トークン`・`finding件数`。

**設計するスパン階層**
```
run (root)
 ├─ plan
 ├─ subagent:explore   ├ tool:Read ├ tool:Glob ├ tool:Grep
 ├─ subagent:security  ├ tool:WebSearch …
 ├─ subagent:cost
 └─ synthesize → output(JSON)
```
- **Trace replay / visualization（preview）** でこの階層を再生し、「どう結論に至ったか」を見せる＝デモ幕2の素材。
- **Evaluations with intelligent sampling（preview）**：本番トレースの一部を賢く抽出して継続評価（全件評価のコストを避ける）→ 設計上「サンプリング率」を設定値に。

### B2. Evaluate — ポリシーを評価に変える（evaluation.py + evals/ 設計）

**2系統の評価を併走**させる設計。

**(a) ASSERT（OSS・inner-loop・安全性重視）**
- **入力＝組織ポリシー**。WAFの観点や「Critical指摘は必ず remediation を伴う」等を YAML 化。
- ASSERT が **評価シナリオを自動生成** → 欠陥（ポリシー逸脱・不安全出力）を本番前に検出 → 制御適用 → 再実行で before/after を提示。
- 任意フレームワーク（LangChain/CrewAI/LiteLLM/OpenAI…）対応＝「Foundry外でも回る」ことを強調。

`evals/policies/security.policy.yaml`（**設計スキーマ（項目定義）**）
```yaml
# 実装はご自身。これは契約となる項目セット
policy:
  id: security-baseline
  intent: "公開到達性・認証・暗号化のリスクを検出し、各 finding に remediation を必須化する"
  requirements:
    - id: public-blob
      must: "公開Blobアクセスが有効なら severity>=High で検出する"
    - id: remediation-required
      must: "security[] の各要素は空でない remediation を持つ"
  generation:
    scenarios_per_requirement: 5      # ASSERTが自動生成するテスト数
  scoring:
    fail_on: ["missing_remediation", "missed_public_blob"]
```

**(b) Rubric（Foundry-native・production品質・スケール）**
- エージェント定義とユースケースから **重み付き品質基準を自動生成** → 2段階（rubric生成→採点）。
- 出力は **統合スコアカード**。**Agent Optimizer に直結**（B4の入力）。

`evals/rubrics/analysis-quality.rubric.yaml`（**設計スキーマ**）
```yaml
rubric:
  dimensions:
    - name: coverage      # 主要リスクを取りこぼさない
      weight: 0.35
    - name: actionability # remediation/推奨が具体的か
      weight: 0.30
    - name: accuracy      # 設定の読み取りが正確か
      weight: 0.25
    - name: prioritization # severity付けが妥当か
      weight: 0.10
```

**(c) 会話品質の評価（preview機能を設計に組み込む）**
- **Multi-turn evaluation**：複数ターンの劣化・安全性を評価（単発応答では出ない問題）。
- **User Simulation**：現実的なマルチターン会話を自動生成して耐性を測る（`evals/scenarios/`）。
- **Traces-to-dataset**：本番トレースを構造化評価データセット化し、オフラインのテスト網羅を上げる。

### B3. Control — ACS で決定論的ガードレール（control/acs.policy.yaml + control/acs_runtime.py 設計）

**ACS = エージェント安全制御のオープン標準**。「MCP/A2A の安全版」。5チェックポイントに**決定論的**制御を、**ポータブルな YAML 契約**で置く。

| チェックポイント | このエージェントで置く制御（設計例） |
|---|---|
| **input** | 投入されたAzureエクスポートの PII/機微情報フィルタ、サイズ上限 |
| **LLM** | jailbreak 検出、タスク逸脱（task adherence）チェック |
| **state** | session 跨ぎで持ち越して良い情報の制限 |
| **tool** | Bash/Write の許可範囲、外部到達（WebFetch）先の制限 |
| **output** | finding に remediation 必須・社外秘表現の遮断・スキーマ準拠検証 |

`control/acs.policy.yaml`（**設計スキーマ・項目**）
```yaml
acs:
  version: "1.0"
  checkpoints:
    input:  [ { control: pii-filter }, { control: max-size, limit: "5MB" } ]
    llm:    [ { control: jailbreak-detect }, { control: task-adherence } ]
    tool:   [ { control: allow-tools, only: ["Read","Glob","Grep","Write","WebSearch"] } ]
    output: [ { control: schema-validate, schema: "analysis-output" },
              { control: require-field, path: "security[].remediation" } ]
```
- **設計の効きどころ**：ACSはコード外の宣言で、security がレビュー→どこでも適用。`acs_runtime.py` は各チェックポイントで policy を読み制御を発火させる薄い実行系。
- 補助：**Guided Guardrail Setup（preview）** で初期ガードレール推奨を生成→ acs.policy.yaml の出発点に。**Runtime DLP（Purview, preview）** で prompt/tool callの機微データを実行時に遮断。

**閉ループ（Part B の中核ストーリー）**
```
ASSERTで欠陥特定 → ACSで該当チェックポイントに制御 → ASSERT再実行で改善を確認（before/after）
```

### B4. Optimize → ROI（observability/roi.py + Optimizer 連携 設計）

**Agent Optimizer（private preview）**
- 本番トレース＋評価（Rubric等）を **Foundry AI Operations 内で実行**し、**ランク付き・レビュー可能な改善提案**を Optimizer に返す。
- 設計上の接続：`evaluation.py` のスコア → Optimizer 入力。改善提案を1つ適用→再評価でスコア上昇を見せる（デモ幕3）。
- **Procedural Memory（preview）**：実行を跨いで「やり方」を学習（Tau-bench で +7〜14%）。最適化の一手段として設計に含める。

**Agent ROI（private preview）— `roi.py` の算出設計**
3指標を、固定出力スキーマ（A3）とトレース（B1）から機械的に算出できるよう設計する。

| 指標 | 定義（設計式の考え方） | 必要データ源 |
|---|---|---|
| **Task completion rate** | 期待スキーマを満たし、ポリシー逸脱なく完了した割合 | evaluation.py のpass/fail |
| **Time saved** | 手動WAFレビュー基準工数 − エージェント実行時間 | ベースライン定数 ＋ トレースの所要時間 |
| **Cost efficiency** | (削減コスト＋工数価値) ÷ (トークン/実行コスト) | findingのestimatedSavings集計 ＋ トークン計測 |

`roi.py` 設計メモ
- `summary.costSavingsOpportunities` と各 `cost[].estimatedSavings` を集計し、**「このエージェント1回で見つけた潜在削減額」**を出す（顧客に最も刺さる数字）。
- 手動レビューのベースライン工数は **設定値（例：1サブスクリプション=N時間）** として外出し（顧客ごとに差し替え可能に）。
- **Azure Monitor と評価/トレースを束ねて**ダッシュボード化（NTT DATA 事例が示す「観測＋継続最適化でエンタープライズ化」の型）。

### B5. Part B 単体コンテンツの「読み筋」（docs/trust-roi-deepdive.md）
1. なぜ出荷後が本番か → 2. Observe（Hooks→トレース） → 3. Evaluate（ASSERT=ポリシーを評価に / Rubric=品質スコア） → 4. Control（ACS 5点） → 5. 閉ループ（before/after） → 6. Optimize→ROI（削減額・削減時間）。
> これだけで「任意フレームワークの統制とROI」のセッション1本になる（BRK250/BRK252 に対応）。

---

## 3. ファイル別 実装設計表（path → 責務 → 入力 → 出力 → 依存）

| path | 責務 | 入力 | 出力 | 依存 | 区分 |
|---|---|---|---|---|---|
| `src/agent/main_agent.py` | 計画・委譲・`query()`駆動 | プロンプト＋作業FS | 構造化JSON | Claude Agent SDK / .claude定義 | A |
| `.claude/agents/*.md` | SubAgent定義（許可tool含む） | — | — | SDK | A |
| `.claude/skills/azure-well-architected/SKILL.md` | WAF 5本柱の段階ロード知識 | — | — | SDK Skills | A |
| `src/agent/server.py` | Hosted Agent エントリ／プロトコル受け／session・FS・identity・approval橋渡し | Responses/Invocations | レスポンス | Foundry runtime / Claude SDK / MAF optional | A |
| `.foundry/agent-metadata.yaml` | Foundry メタデータ／identity・sandbox・scale・guardrails・観測フラグ | — | — | Foundry Hosted Agent | A |
| `infra/`(azd/bicep) | デプロイ・Managed Identity・RBAC・監視・endpoint/scale | パラメータ | リソース | azd / Azure | A |
| `src/agent/observability/tracing.py` | Hooks→スパン→Azure Monitor/Foundry | Hooksイベント | トレース | OTel/Azure Monitor | B |
| `src/agent/observability/evaluation.py` | ASSERT/Rubric 実行・集約 | 出力JSON＋policies | スコアカード | ASSERT/Rubric | B |
| `evals/policies/*.yaml` | ASSERT ポリシー | — | — | ASSERT | B |
| `evals/rubrics/*.yaml` | Rubric 定義 | — | — | Rubric | B |
| `evals/scenarios/*` | User Simulation/multi-turn | — | 会話 | preview eval | B |
| `control/acs.policy.yaml` | ACS 制御契約（5点） | — | — | ACS | B |
| `src/agent/control/acs_runtime.py` | 各チェックポイントで制御発火 | policy＋実行イベント | allow/block | ACS | B |
| `src/agent/observability/roi.py` | ROI 3指標算出 | 出力JSON＋トレース＋基準値 | ROI指標 | Agent ROI/Monitor | B |
| `example/bad-config/` | 必ず指摘が出る入力 | — | — | — | A/B共通（デモ主役） |
| `docs/harness-deepdive.md` | Part A 読み物 | — | — | — | A |
| `docs/trust-roi-deepdive.md` | Part B 読み物 | — | — | — | B |

---

## 4. 段階的実装ロードマップ（マイルストーン）

> 既存ロードマップ（backend scaffold → Main/SubAgent → WAF skill → ローカル分析 → Hosted entry → tracing/eval 基盤）を踏襲し、Part A/B を積む。

- **M0（土台・既存範囲）**：backend scaffold / Main Agent / `.claude` 定義 / WAF skill / sample分析 / Hosted Agent entry。
- **M1（Part A 完成・"作って載せる"）**：出力スキーマ固定 → server.py の Responses/Invocations 対応 → session/FS/identity 橋渡し → sandbox FS persistence デモ → approval checkpoint → Hosted Agent guardrails → azd デプロイ → `agent-framework-claude` ラップ例1本 → `docs/harness-deepdive.md`。
- **M2（Part B-Observe/Evaluate）**：tracing.py（Hooks→OTel/Monitor）→ trace replay 確認 → ASSERT ポリシー3本 → Rubric → evaluation.py で before/after。
- **M3（Part B-Control）**：acs.policy.yaml（5点）→ acs_runtime.py → Guided Guardrail で初期値 → Runtime DLP。
- **M4（Part B-Optimize/ROI）**：Optimizer 連携 → roi.py（3指標）→ Azure Monitor ダッシュボード → `docs/trust-roi-deepdive.md`。
- **M5（仕上げ）**：frontend / MS Learn Docs MCP / Routines 定期実行デモ。

---

## 5. デモ導線との対応（3幕 ↔ 機能）

| 幕 | 見せるもの | 効かせるPart/機能 |
|---|---|---|
| 幕1 刺さる入力 | `example/bad-config/` 投入→SubAgent委譲→sandbox FSへ中間成果物保存→approval後に構造化レポート | Part A（Claude SDK inner harness + Hosted Agent managed harness） |
| 幕2 信頼の可視化 | トレース再生＋ASSERT before/after＋Rubricスコア＋ACS発火 | Part B（Observe / Evaluate / Control） |
| 幕3 ROI | 削減額・削減時間・完了率、Optimizer提案適用で再評価スコア上昇 | Part B（Optimize / ROI / Procedural Memory） |

---

## 6. 単体成立のためのチェック（各Partを独立コンテンツにする条件）

- **Part A 単体**：M1まで＋`docs/harness-deepdive.md`＋幕1デモがあれば、「Claude SDK の agent runtime を、Hosted Agent の sandbox / identity / persistence / scale / observability / guardrails に載せる」技術セッションとして成立。ROIに触れずとも完結。
- **Part B 単体**：固定出力スキーマを持つ任意エージェント（Claude製でなくても可）＋M2〜M4＋`docs/trust-roi-deepdive.md`＋幕2-3で、「任意フレームワークの統制とROI」セッションとして成立。Part B は **ASSERT/ACS が OSS・フレーム非依存**ゆえ、他社FW顧客にもそのまま当てられるのが強み。

---

## 付録 A. 一次情報リンク
- What's new in Microsoft Foundry | Build Edition — https://devblogs.microsoft.com/foundry/whats-new-in-microsoft-foundry-build-2026/
- Build and run agents at scale — https://devblogs.microsoft.com/foundry/agent-service-build2026/
- What's New in Hosted Agents — https://devblogs.microsoft.com/foundry/hosted-agents-build26/
- Introducing the new Hosted Agents in Foundry Agent Service — https://devblogs.microsoft.com/foundry/introducing-the-new-hosted-agents-in-foundry-agent-service-secure-scalable-compute-built-for-agents/
- Agent Harness in Agent Framework — https://devblogs.microsoft.com/agent-framework/agent-harness-in-agent-framework/
- From local to production: deploy your Microsoft Agent Framework agent with Foundry Hosted Agents — https://devblogs.microsoft.com/agent-framework/from-local-to-production-deploy-your-microsoft-agent-framework-agent-with-foundry-hosted-agents/
- Azure AI Foundry Agent Service overview — https://learn.microsoft.com/en-us/azure/foundry/agents/overview
- Build agents you can trust（open evals + control standard） — https://devblogs.microsoft.com/foundry/build-2026-open-trust-stack-ai-agents/
- Claude Agent SDK overview — https://code.claude.com/docs/en/agent-sdk/overview
- 既存リポジトリ — https://github.com/ishidahra01/claude-agent-accelerator-on-foundry
- 関連セッション：BRK243（Claw and agent harness）/ BRK250（OSSエージェント統制）/ BRK252（observability→ROI）/ LAB540（Hosted Agentの観測・最適化・保護）

## 付録 B. 用語の一行定義
- **Hosted Agent**：任意フレームのエージェントをサンドボックス・state・filesystem persistence・identity・scale-to-zero・observability・guardrails付きで Foundry が本番ホストする runtime（GA見込み 2026/7初旬）。
- **Harness（agent harness）**：エージェントを動かす土台＝agent loop・tools・memory・middleware・shell/filesystem・approval・状態管理をつなぐ実行基盤。Claude Agent SDK は内側の agent runtime、Foundry Hosted Agent は外側の managed harness を担う。
- **ASSERT**：組織ポリシーを評価に変換するOSSの評価フレーム（安全性重視・任意フレーム）。
- **ACS（Agent Control Specification）**：入力/LLM/state/tool/出力の5点に決定論的制御を置くポータブルなYAML制御標準（OSS）。
- **Rubric**：エージェント文脈から重み付き品質基準を自動生成する Foundry-native evaluator（Optimizerに直結）。
- **Agent Optimizer / Agent ROI**：本番シグナルから改善提案を返す最適化器／task完了率・削減時間・コスト効率でビジネス価値を測る計測（ともに private preview）。
