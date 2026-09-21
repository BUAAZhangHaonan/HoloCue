# 当前结论：限定静态问题已闭合

最终局部复查版本SHA256：`99db3e129659e824eed7fe037f3cb9e60139e23eb91ea409669df85f97e6f929`，本地与4029一致。仅检查要求的修正行：第30行现在为 `sealed_manifest=json.loads(archive.read('HoloCue_Review/MANIFEST.json'))`，与先前独立读取的真实ZIP成员一致。

本次发现的两项P2及后续ZIP成员路径阻断均已在代码层修复，原safe_file返回Path、hashlib.file_digest的运行时兼容已核实。当前没有本限定静态审阅范围内的未闭合问题。

此结论不表示选择器已经执行成功，也不替代最终inherited_evidence_verification、selection、视频派生proof和新ZIP检查。后续最终产物另行审查；本轮未运行选择器或重复扫描资产。以下历史发现保留以便追溯，不代表当前仍有阻断。

---
# 两项修复局部复查

复查版本SHA256：`0673d42c2c54bd938d2cf547fbb639dd2a20a158f0708bb13c91e28fbfbb5032`，本地与远端一致。本轮没有运行选择器，也未扫描全部资产。

- 原P2“current只看assets_after”：56行已正确改为assets_before == assets_after == 当前，代码层修复。
- 原P2“旧证据未锚定封存字节”：22–49行新增index ZIP size/SHA检查及继承文件逐项size/SHA核对，生成inherited_evidence_verification，修复思路正确；但新增一处成员路径错误阻断实际执行。

**P1，30行：archive.read('MANIFEST.json')找不到实际ZIP成员。** 已只读列出原00_review_index.zip成员，准确名称是 `HoloCue_Review/MANIFEST.json`。当前写法会在进入继承验证前抛KeyError。最小修复为使用该完整成员名，保持原ZIP不动。

运行时兼容已做独立小范围确认：项目.venv-simulation为Python3.12.7；原bundle.safe_file(root,'README.md')实际返回PosixPath且isinstance(Path)=true；hashlib.file_digest可调用，读取README.md的结果与hashlib.sha256(read_bytes())相同。故path.open()/file_digest没有类型或版本兼容阻碍。只读ZIP成员清单和一个小文本散列不等于运行交付选择器。

以下保留首次审阅发现；最终应以最新复查状态解释。

---
# 续跑交付选择器独立静态审阅

独立会话：`/root/cloud_provenance_review`。对象：`.work/cloud_resume_20260921/prepare_delivery.py`，SHA256=`20a6ceea0c77aa09f820bba397c0916bb14634bd81b12e7fbfbdc6a7cd64f744`；本地与4029对应文件散列相同。只读审阅，未运行选择器、未改旧RUN/ZIP，未重扫资产和未启动实验。

## 具体缺陷

### P2：继承旧证据只继承路径，未约束封存字节（19–29行）

previous来自旧RUN的review_selection.json，代码把run_id加previous_并把scope/status转成historical/recorded，随后直接把previous.files中的实时项目路径加入新selection。没有读取封存包MANIFEST记录的SHA256来约束这些历史文件。原review_bundle.pack仅对current passed/failed检查来源；历史项只把当前路径字节复制并计算新的哈希。因此旧路径若在封存后发生修改，新包会把新字节归为“Preserved earlier-batch record”，后续ZIP自身校验仍能通过，封存来源却没有得到保证。这是选择器的约束缺口；本静态审阅**没有发现或声称旧文件已经被篡改**。

最小建议：以旧封存00_review_index.zip内MANIFEST（同时校验其对应UPLOAD_INDEX身份）为继承文件的expected SHA256依据；新包复制/散列时核对，缺失或不同即中止。FINAL_RECEIPT、归档复核补录等封存后新增材料单独列明，不冒充旧包成员。可以在复制阶段复用已计算hash，避免无谓重复读大文件。

### P2：current资产身份只检查after（36行）

判断current时要求source_before/source_after都等于当前源码，却只要求assets_after等于当前资产。如果某命令的assets_before不同、执行中将资产改为当前内容，它仍被标为current，其结果可能实际消耗过不同资产。identity(78–83行)虽然保留before/after值，但current分类没有同等边界约束；原pack也只核assets_after，不能代为发现这个误分类。

最小建议：current判断要求assets_before.digest == assets_after.digest == assets.digest；不满足则保留historical/recorded以及原前后摘要，不以after单方匹配晋升。当前续跑基线已经独立确认资产未变，此问题是选择器必须正确处理的判定路径，不是声称当前续跑已发生资产修改。

## 已核对且未发现直接错误的部分

- 对照原Review Kit的Run/Evidence/Selection严格schema，现有字段名和group值兼容；.cjs/.diff同时加入ALLOWED/TEXT，其余原工具规则没有修改。旧run统一previous_前缀，与新run分开，旧失败返回码仍留在原command记录，没有把失败改为新成功。
- 新命令要求execution.json完成后才纳入；selection/export/verify目录明确排除，未将正在运行的任务静态写成完成。未运行的native/pairs仍为not_run。
- 顶层repair_process suffix匹配后break，避免上一轮曾出现的重叠后缀归属错误；bridge_<scene>、pairs_<scene>与run_remaining.sh的实际命名一致。
- 旧selected files保留原group（含三份native blend）、derived_from及derivation_command_record；新视频同时填写derived_from和derivation_command_record，满足原Evidence配对约束。大型原视频没有review index就停止，review copy要求proof.passed，并附original身份；最终还需核实际proof内容/时长/尺寸/帧数及选入视频，静态代码不能代替这些证据。
- 新run文件遍历不只选成功报告，原始日志/失败状态/图片/视频都可纳入；排除的是SQLite、分层PNG和frames中间文件（保留manifest），符合已声明交付范围。消费帧等独立JSON不在上述frames子目录排除条件时会选入。
- 当前源码、活动GLB及fixture由原pack自动添加，不能因selection.files里未手写每个GLB就判漏选。当前tools三文件通过旧selection继承，但其旧摘要同样需要第一项的封存身份约束。
- 旧COVERAGE被嵌入reused_checks/earlier_batch，并附旧命令路径和旧source/assets摘要；没有把旧blocks/519/geometry/labels改称本轮执行。
- FINAL_RECEIPT.json及两份provenance_archive_review补录在旧RUN存在；add仍会静默忽略缺文件，因此最终selection应核对这些预期附件确实在列表中。

## 本次边界与待验

本审阅没有运行prepare_delivery，不签署尚未生成的最终selection或视频派生proof通过。修复上述两个判定后，最后应只核新selection及封存身份、当前运行完成记录、实际视频和文件覆盖；新ZIP成员hash/CRC仍在打包后单独验。旧18ZIP已完成独立复核，本次未重扫。

读取的相关代码：本地prepare_delivery.py和run_remaining.sh；4029原Review Kit review_bundle.py的Run/Evidence/Selection、current与historical执行来源校验规则；读取目录仅为确认真实命名和指定补录文件存在。