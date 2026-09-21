# 已封存ZIP独立完整性复核

独立审查会话：/root/cloud_provenance_review。时间：2026-09-21T12:45:52.562449+00:00。

**结论：通过。** 独立读取本批全部实际ZIP，逐包SHA256、大小、CRC及全部成员SHA256/大小与UPLOAD_INDEX、SHA256SUMS及包内MANIFEST一致；未发现遗漏、额外或重复成员。复核不解压、不改封存ZIP、不运行项目实验。

- ZIP：21份，共393.55 MiB；最大44.28 MiB，全部严格小于48 MiB。
- 项目成员：2234；索引成员：6；合计独立核验2240份。
- 最终源码摘要：37b81f92c4bb91b5ca68180be99b1f1810b40657842cf2d3145bd1eeb8d3f0fe。
- 本次计数与既有LOCAL_VERIFICATION一致；哈希及CRC由本独立程序重新计算，未照抄既有passed字段。
- 封存主报告“ZIP待验”符合当时事实；本补录补足包级核验，不修改原ZIP。
- 包级完整性不改变实验结论：519测试属于b2阶段，blocks完整通过，本批CNC十八阶段完整通过，connector模型连接失败、0阶段；另5场及3组pairs未运行。

目录：C:\Users\zhn19\Downloads\2\HoloCue_Cloud_Resume_20260921

完整逐包/逐成员实际哈希见provenance_archive_review.json；该JSON SHA256：29d4d0d1c3ccd25dabedb1207406800244dd76e1488181e36ce14b69728ce6e1。
复核程序为provenance_archive_review.py。

| ZIP | MiB | 成员数 | SHA256 |
|---|---:|---:|---|
| 00_review_index.zip | 0.15 | 6 | 8743ec3ecafe36c77d6fdd7180dc336270e438e76039cadc23f28421ea9198df |
| 01_source_reports_001.zip | 4.87 | 339 | ef7e3a62aebe69169d990c1e47602681532c507b8e2ca3bc6746dd766199e2b2 |
| 01_source_reports_002.zip | 6.13 | 217 | c90b4c9f1a4cc00db0364927ab1dca4007d3fb8efcc727b4b4b67348ed994e1b |
| 01_source_reports_003.zip | 5.73 | 198 | eede77ca28f723e4505a5bf5f7040dd090dfbbef3ff8a43a5fd6476df92dfab6 |
| 01_source_reports_004.zip | 5.09 | 113 | 6dd1000aada7bdc61e8437fe68cf93f2dc22cf49432d457c6a18e6c467d82927 |
| 01_source_reports_005.zip | 5.83 | 811 | ad36411108b9c8c787fbacfdee03fe501793fdd62fb3790036c6049f86c3dc68 |
| 02_visuals_001.zip | 44.28 | 104 | bf7a845effc7ff2cbee15b5f89138961f11c3ce53cd4ec0f8f3d814dd762482e |
| 02_visuals_002.zip | 31.04 | 12 | 0539e32e9ff7007e997e4a23661caeac1923d51123b6eeb63dcff6e966b375dd |
| 02_visuals_003.zip | 34.41 | 69 | 5b1fdfbfbc3a5a2bd9344b07d4d14391db4900145e56e841570060f83a856ab0 |
| 02_visuals_004.zip | 23.66 | 26 | 1c356cc668a039206e85e9b8011ab0c31000867cf4a89100e8efb36103d4b06f |
| 02_visuals_005.zip | 33.45 | 45 | a3bff31083bc314da21158d9e0d63ab4421aa1ba549250e46859dc8aa724b30f |
| 02_visuals_006.zip | 32.21 | 22 | c0b736156ebea8ac20f67feea8042113d0c41e23adbbaa3beb9baf1702bf6e68 |
| 02_visuals_007.zip | 40.59 | 131 | 580bc2b9efda6cfe1a1847bb57ead87b5f774cd1040beb05baea5a4d331173d2 |
| 02_visuals_008.zip | 20.49 | 41 | 86117f50cf36cb69736c5717b767747964b379df554ca02d3382e3194074d607 |
| 03_assets_001.zip | 14.24 | 50 | 373b028ed765c001d0f1ecbb59b3d4916d21b95cd908a46ccf665a495012f42f |
| 03_assets_002.zip | 18.00 | 20 | 9e9cc2eeb92a8a0db19d307e61d45b1fee2bbe3a558ebd47c320c6d7f189ec46 |
| 03_assets_003.zip | 13.75 | 22 | 93df3c21dd1e9fc8f885d977ad02f331246169a9fd0a3a8295814c99f034b9a6 |
| 03_assets_004.zip | 9.50 | 11 | effd3d0c17dfa8a06d45b2eec35b1b00e7e13c5e0355344cba3725593142eb43 |
| 04_native_001.zip | 7.25 | 1 | 6529a021d7c2753065b8c3c74877ee7f092bd909d3d76ca17584f80a54637924 |
| 04_native_002.zip | 25.36 | 1 | 419007a6cdcea02df76898c76d939747123d6979e680fad24c4d05596076b97e |
| 04_native_003.zip | 17.50 | 1 | 6fe58987725bd3fe6b7870b62415edcdd230b2aa5b7a869f0d08d989c5113704 |

## 原输入文件身份

- UPLOAD_INDEX.json: 0d79918af5b9f4d52cb0984060e9f6d438e00e6909b99a1585005a9b6389a65b
- LOCAL_VERIFICATION.json: 865ad54b433a1eb86a6e3ba7801b8919c5873fbe8b7458f53120a3ba00b7f0fc
- SHA256SUMS: 490fa5afaf858b8183a21e01ffdb292b6a37de4adc988c61f3a4f127860481b5

## 续跑必需内容与最新报告核验

直接从新ZIP的MANIFEST及实际成员复核：

- 新RUN的FINAL_SUMMARY、COVERAGE、inherited_evidence_verification和CNC/connector原始事件文件均在包中。
- CNC十八阶段的36张原始frame_0000.png/viser.png及2份本批原始WebM完整纳入；两个原始事件文件hash与本独立会话封存前读取一致，包含已审阅真实模型回复及connector失败证据。
- 103项资产/fixture的hash和bytes全部与本轮独立实际散列基线一致；3份native blend与先前已核构建产物hash一致。
- 1582份继承文件在新包内的实际hash/bytes全部匹配inherited_evidence_verification；没有继承内容差异。
- 包内COVERAGE保留CNC returncode0/18阶段/passed=true及connector returncode1/0阶段/passed=false，不将失败或未运行改写为成功。
- 包内三份独立报告均为最后审阅版本，完整hash如下。

| 已封存报告 | SHA256 |
|---|---|
| .work/cloud_resume_20260921/code_review.md | ad294f5ceff88063424606190cd99f0bb8c3842757c070e3e9abb2b502a8c37b |
| .work/cloud_resume_20260921/visual_review.md | 4cbf3f4121cac178f34137405826df8006786803de4f9c723cfb76df534d780b |
| .work/cloud_resume_20260921/provenance_review.md | 818b09d11e40b715ae6551d2d5b58e44eda45d1338485bffe197677ea5ac10ce |

FINAL_SUMMARY.md包内hash为ebd0adabce3a8283f87e51cc57c0e755d29bc3619b6b5d7ed40c0a8a10ba4f52；COVERAGE.json包内hash为5451648b0809d86e6540945175a1140cd25850528817c5c3ed64f4da296ec9d4。以上均为实际封存包内容，不是仅检查服务器同名文件。

本补录和JSON作为封存后独立附件交付，旧包、本次已封存ZIP及其中三份审查报告均保持不变。