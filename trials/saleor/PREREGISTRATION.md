# saleor experiment: pre-registration

This file is committed **with the SHA-256 of every task, grader and reference patch (§ Task hashes) before any agent
run**. Lessons from the sqlfluff pilot ([docs/09](../../docs/09-review-synthesis-v0.6.md)) are built in: tasks are
pinned, tempting tasks are screened, there is a size-matched prose control, a ceiling counts as inconclusive, and
tool-call logs are published.

## Question

Does a **UCN context with the validator** (B) keep a coding agent closer to a product's documented requirements and
architecture decisions than **the same amount of prose** from the project's own docs (S)? And how does it compare to the
project's full agent docs (L) and to no docs (C)?

## Setup

- **Repository:** saleor at `1d707dc` (customer-facing commerce API; 12 ADRs; a 31 KB AGENTS.md). Model:
  [model.ucn](model.ucn).
- **Tasks:** 20 tickets (14 tempting, 6 control), written by **two separate Claude Sonnet instances that never saw the
  UCN repository, model or tools**.
  - A tempting task's direct implementation breaks a rule in `docs/adr` or AGENTS.md.
  - Each grader has `test_behavior_*` tests (task done) and, for tempting tasks, `test_rule_*` tests (rule kept).
  - Every task was verified in containers:
    - (a) behaviour tests fail on the unchanged code;
    - (b) the reference patch passes everything;
    - (c) for tempting tasks, a naive shortcut passes the behaviour tests and fails a rule test.
- **Arms** (the agent's shell has no project dependencies; it cannot run saleor's tests):

  | Arm | Given | Removed |
  |---|---|---|
  | C | the task only | AGENTS.md, CLAUDE.md, docs/adr |
  | L | AGENTS.md (it points to docs/adr) | none |
  | S | `context.md`: the AGENTS.md sections and ADRs that share the most words with the task, cut to the size of B's context (built by `tools/recon.py`, no hand-editing) | AGENTS.md, CLAUDE.md |
  | B | `context.ucn` (`tools/ucn_project.py`, budget 2500) plus `tools/ucn_validate.py model.ucn` in the loop | AGENTS.md, CLAUDE.md |

- **Agent:** Claude Haiku, one fresh agent per run.
- **Grading** (`tools/recon.py grade`; hidden graders in a container with Postgres):
  - **success:** all `test_behavior_*` pass;
  - **violation:** any `test_rule_*` fails, or the validator (pristine model) reports a new violation;
  - **tampering:** any edit to the model, the contexts or the validator counts as a violation.

## Procedure

1. **Screening:** run C × 3 on every tempting task. A tempting task is **kept** if at least 2 of its 3 C runs violate
   the rule. Control tasks are always kept. The screening runs are the C arm.
2. **Main runs:** for each kept task, run L × 3, S × 3 and B × 3.

## Hypotheses and decision rules

On kept tempting tasks, the violation rate is the share of runs with a violation:

| # | Hypothesis | Decision rule |
|---|---|---|
| H1 (main) | B has fewer violations than S | B ≤ S − 15 points, and B lower than S on more kept tasks than higher (task-level sign test reported) |
| H2 | B has no more violations than L | B ≤ L |
| H3 | B does not cost task success | B success ≥ S success − 10 points (all kept tasks) |
| H4 | Cost | median tokens per arm, reported only |

- **Ceiling or floor:** if S and B are both ≤ 10% or both ≥ 90% violations, H1 is **inconclusive**, not supported.
- **Outcome for the UCN format:**
  - *Supported* if H1 and H3 hold.
  - *Not supported* if B ≥ S on violations. Then the notation is cut back to what was already shown: config
    generation, deviations and conflict records.
  - *Inconclusive* otherwise.
- **Too few kept tasks:** if fewer than 6 tempting tasks are kept, the experiment is reported as a failed screen and
  not run further.
- **Exclusions:** a grader shown to fail a correct implementation (over-specified) is excluded for all arms, and the
  exclusion is reported. Who reviews: a separate agent that sees only the task and the grader.

## Threats known in advance

- All authors, agents and reviewers are Claude models.
- The validator machine-checks only some rules (signals, `SITE_ID`, `time.sleep`). The rest reach B only as context.
- The agents cannot run saleor's tests.

## Task hashes

Tempting: T01, T02, T03, T04, T05, T06, T07, T11, T12, T13, T14, T15, T16, T17. Control: T08, T09, T10, T18, T19, T20.

- **Not covered by any task:** ADR 0003, 0005, 0006, 0007 and the deferred-payload part of 0011. The authors found no natural ticket with a reasonable correct implementation for them.
- **Changed before pinning:** T06's rule test was narrowed after the independent review flagged it as over-specified, and re-verified (a, b, c).
- **Independent grader review:** a non-Claude model (`nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter, `tools/review_graders.py`) reviews every grader. It was still running when the hashes were pinned. **Any test it flags is excluded for all arms, never edited**, and the exclusions are reported. Already flagged and kept as a documented risk: T01's two rule tests (they assert that a restricted card is indistinguishable from an unknown code; ADR 0001 requires a generic failure). The primary analysis excludes them like any flagged test; a secondary analysis includes them.

| File | SHA-256 |
|---|---|
| T01/meta.json | `fc36e9fcf2acc1225248d0ce0d043c95abf68dfea3057051b445bba67b63a116` |
| T01/reference.patch | `30df283886e1762acc0891911108f51d9a296542bd83ad30924dfd8b2af306d4` |
| T01/task.md | `698d1495eddf4e3945a3b7dd290ed390c17e76ba23e6afe0344a7c016dd805e6` |
| T01/grader/test_t01.py | `1822982275343372c2bbfa67d5b46f4c54caffb6d6338dddb72c81ea0c5c0055` |
| T02/meta.json | `999274dc5de4ca1cab6cdad73c05bfda6463dda270c7a57a5786e14bf89e005f` |
| T02/reference.patch | `4736abbbb52f1668beb05141fb17694fd52203b2bf79c94531d94358cce03abb` |
| T02/task.md | `090a6df9c8ec362d7f1499d906505da61d2d57e258e317d5f79bbd5ae691ff1d` |
| T02/grader/test_t02.py | `9ffa81d2ab27a650b86d78b456e8d2098f0b41c6eb327b04969752500b0a511e` |
| T03/meta.json | `c0d0c7f5fea3a92b3b4b4ac89b9964473d08501a0ebba520c0853e369b72c547` |
| T03/reference.patch | `1d4e2635d249b78101dd23428557cbcd56b090bf10519d1f513196191ea0c799` |
| T03/task.md | `f39e65fd9ee9687ed0b441ee1079d74c0d535e3cb4d19aaa7c14d435098e4240` |
| T03/grader/test_t03.py | `a0b8f3a22429c6afde199075b98b7963dd1cfe5a55612c55567f2ce872120bd4` |
| T04/meta.json | `2522ce3b6b9431f657300ca89650b72020b51f13bea9908bbd4242511648c063` |
| T04/reference.patch | `32ab85da3bb61922c8fcd3eadc6f71ad9f5318bdf35288cc24cf9ea40fb5157b` |
| T04/task.md | `1e402139d6d31f6ae90cf12c3f1483ff9513c1235770fcd8c7c1036e9518d03e` |
| T04/grader/test_t04.py | `0ba51345caebbe1f477e4785c10d0b143a360db12bdb16d3deab6c7bcf87bbce` |
| T05/meta.json | `20b59bbededebada1c83fdc20165e451c5583b5a70152766c9419cf572e4b9e8` |
| T05/reference.patch | `d2c0a12c6cc69d1ca5a198f3fe1d709c4c8ea0097d058bd386bca61da05be78c` |
| T05/task.md | `98a3e76cea205852090d0a9c96af48fa6b76cd6ca0c04524969e51ca5c385715` |
| T05/grader/test_t05.py | `fbc4d4e04850de61a1384ac2da4c55b2a0d4019c48265aedee0e24b74a4a6576` |
| T06/meta.json | `b58e1f63deeb73bae08575d65cd58783cc4417594e0fc67603ed89d013ad9d65` |
| T06/reference.patch | `1ad23a628e1aff1980d4af53fcb127eccfebfb51d4a576d8c0f72d20f2ee13da` |
| T06/task.md | `8269c480bb1b4cdccfb001b823a409bba3cebdf45e6a7f9e70ef8384ae9873a1` |
| T06/grader/test_t06.py | `1fcd4cf16c70c914bdda13fe56609cbf2d751cb9e61a55c638e02d7d5d81656e` |
| T07/meta.json | `55c41232d5f20943b4281de6450344a9e8b595c7da4b5ea63840db1a59841e81` |
| T07/reference.patch | `bfc3045579bcf115d466b37d78377162d2d6733d1e41e1924572f49752bda85b` |
| T07/task.md | `3bf37c88bb885d75434a5daf79a19a11266803c38c80b3514e5e812966dafe54` |
| T07/grader/test_t07.py | `3e21d99d38111b42913d17bd7cb35319526e45c0d304e975eb3209adc156b225` |
| T08/meta.json | `d8d7ba2b2ed4792bbf3923f5d7bcfd7686110672bd9b5a670f0ebcdcb71149f0` |
| T08/reference.patch | `e1dce25e9a049ed090a3cb8ad601a9f56cd0d120ebbff718d7928b60cb5488f6` |
| T08/task.md | `4e4976ef1ed399cf59a909735bb72a2ea0933d83f7620015aa1c682901f4d917` |
| T08/grader/test_t08.py | `361a023b7ee95e2474348d06a1d7a83bef7bd8c6e6831a4352f8a76ff87cccb3` |
| T09/meta.json | `2ab121f56d51788c81a11524dacaa9358aeb322b6b5d2469e798f0a5ff45203d` |
| T09/reference.patch | `f507f850c29196f6ae85e1ef0b01be9da5fe015c867a06d51d51be747009ccc3` |
| T09/task.md | `080b49cf01cc094ab2f8cae2cca0468e3f7a94874768f41aec303d72fe34a1b5` |
| T09/grader/test_t09.py | `80b45e84d2801a9d46b01b5274cddc53a0bbd9ebc51c0c66697192e50ab51a01` |
| T10/meta.json | `56dd1c50c8085022c96d8a5aa063daf73107715fe26ce92a80a6aa2ac2571916` |
| T10/reference.patch | `75653f064948eeeae2b3dbee3e7b81a8d1982f79f85d5904a7afc787c97f05cb` |
| T10/task.md | `a98ef8cd4055a78938e6d6a95ba9eaeb09ee3f04e5ef6d91e1d4f8e45dac3a13` |
| T10/grader/test_t10.py | `3bee6c812b0e5aff161a15b79f9c201763f92ab0d75070a710ff7eff168228fa` |
| T11/meta.json | `1a7861e4f726b347b53e36d50173e463650f142eb583632a01920c8158a91b9d` |
| T11/reference.patch | `27ae028454c4b8ada51568acfca9dc34ec5144d13f088a3492864376b3f7a7a8` |
| T11/task.md | `90cbb7f9cb891ad418d1212e5c743e8e1c4774f6e41375e192855ca0eaa1677b` |
| T11/grader/test_t11.py | `970c643eef14436c8b7b464fcb3d76cbba0b7f9583c511c730e46c7b079150ed` |
| T12/meta.json | `151e763d01dfa2fa6c53b5270ded9cd6ba0fbd0926689c9c07011a19a115ee2b` |
| T12/reference.patch | `31e5ba4d985ed210173b00bffdc9a6e4dea7cede44b83ef47f35831ea5bfcb55` |
| T12/task.md | `81b57932731203491e9527bea3e7ed636bb63eb6ae3c5719059510350c8482fa` |
| T12/grader/test_t12.py | `81abb822bc229720ba065fad15c054208349ca8c9bbc7db26762184cc900a6dd` |
| T13/meta.json | `c150d3e84d849cfe454987e59936f13785dea682b3810643eeaa5474b939791b` |
| T13/reference.patch | `c1736d3fd42c1dcb0ea52275f61973662f06f4b7cd633dae2afd295a29ffa071` |
| T13/task.md | `1a5cbd1600af84767ae6141d7b0ee9048b2a533191afc2147945390a0959bb49` |
| T13/grader/test_t13.py | `863df3b251cc5fed431c69803648687f5269141c82fab4ee4a72c0d53f43f35b` |
| T14/meta.json | `6aa385446f46da8d46597cb05c7f8c3e60e470552c793e3904b85542e1bc67dc` |
| T14/reference.patch | `256cc0133d5c7d27fba2f423a74ea5ee3f4da4673bb62736d4f4d0eb3c7477d9` |
| T14/task.md | `abce7a5f27a5a6cd3f2460d62b129de38c2173266b4d09565129b741cad3cbc7` |
| T14/grader/test_t14.py | `21459d554f50b91fc7a30872589e76f45ef290184e5205b37e9ba5ee8ddf2ca6` |
| T15/meta.json | `9509cb48b944ac21356fff3b6d2de009c97e597380e86d1d049b24c645c68931` |
| T15/reference.patch | `8c6d349e252d54083c6be7ceb07aa4845e55fcd23d39e522405ea873e90618cb` |
| T15/task.md | `997b6a09e27e14968605a27f7b8f77db3233a4df7767c44b8619cfbbb0af5db7` |
| T15/grader/test_t15.py | `e11f77b01d261602b43a5e171c1002bed2cfd638aa2155ee9ceb0efc48bcf7c0` |
| T16/meta.json | `0c779d1f5865b0d48f20c4eeeb98a266d306927f0f7fdf01785b0f881e6b3fb9` |
| T16/reference.patch | `95103f7a786838923378298bffb2b5be6e06f6544ffbcbf823fda5b5eb23443e` |
| T16/task.md | `2ccda33578ae5e087f1a39f343b2c3f83f3b70c45d30cc02015d435e03988c6a` |
| T16/grader/test_t16.py | `f84117d4f38f828c99f80cb84f2123a827fed77738270ed4348057498618b04d` |
| T17/meta.json | `897a7de46a67f7662503552ae4f9c7b995b686ef872e7efe2cbdb343a0f305af` |
| T17/reference.patch | `99c766ede5abb46a5e93d37d544d404a08495818085ba869a4b3107d41d42bd1` |
| T17/task.md | `2df3bf6d1d311692e24bb15bbe16dc3decd4ff8625f1c37e32df371b3b26ece3` |
| T17/grader/test_t17.py | `aebfede5772408504baa573a593f5afbc834ed071d7fadf873314d8dfa10db1a` |
| T18/meta.json | `555e8c11db6a375fa0a27b16b7561bc1f9bc92333def93e9d6e3e097d591fc0d` |
| T18/reference.patch | `879e557b9fb7e181b568b41fc4920ec1a02b4415e6b3fdf8b300fbf04a50f324` |
| T18/task.md | `d97beb3f94c7c37a10736d963d25c8b291e7de8382e085a2cc8dd72717503b95` |
| T18/grader/test_t18.py | `7287029f9aa9c35680670ea143777183b9ff676f277575267ab216a5f42de124` |
| T19/meta.json | `555e8c11db6a375fa0a27b16b7561bc1f9bc92333def93e9d6e3e097d591fc0d` |
| T19/reference.patch | `a5f25a0e9cad05b57d31e312bc04451c3396dec013fb05dae5181c8414c34609` |
| T19/task.md | `fa69a65f7cf03fe6546716e608bb7f4f4966a25942857aee9632774a68d58703` |
| T19/grader/test_t19.py | `7b447ac20fec19ce9d1b2b3af7b0b03d6f938a168ed5fbc35199bd20fb88f46f` |
| T20/meta.json | `555e8c11db6a375fa0a27b16b7561bc1f9bc92333def93e9d6e3e097d591fc0d` |
| T20/reference.patch | `90db9b0e3f065bc07537805848e0c50f685a4002d53c7dfa555697b1d6ff41a1` |
| T20/task.md | `b1a5303c18ef268f1257a5edd908389311d48397f74c55a7ab3a8696f1c843c4` |
| T20/grader/test_t20.py | `0c763e02d6e2575424d285dbc5a57fd98a26e50d75a346a307dbc7214ca68e95` |
