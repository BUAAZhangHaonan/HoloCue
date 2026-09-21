# resume01服务generation独立快审

会话`/root/cloud_provenance_review`。仅静态读取、AST解析和原record.py参数核对；未执行start/check/readiness/stop。当前service_generation.py SHA256 `3d89456af78ac567ceac749b6278d06c8f5dc32f7e7a11487b7aedbb753e46c5`；wrapper SHA256 `1c8c33c6633319758bb22a6954ad7a0ba99257d122b831a6dbbdc8cb779fd8c5`。

**结论：发现的停止竞态P2已修复；当前限定静态范围未发现继续启动的阻碍。实际resume01服务与停止结果待运行证据确认。**

start预检generation命名、三个服务端口和整套新命名空间，不复用旧command/launcher/owner/resources；每个服务仍调用原record.py并进入resource_guard。独立读取record.py确认HOLOCUE_RECORD_RSS_GB真实传递为guard参数，model32GiB、API/viewer8GiB；环境要求显式0.90，服务argv保持原模型/API/viewer脚本。wrapper仅调用resume01的PID/create_time与未结束execution边界检查，不启动服务。

旧版本6b6e5b71…的stop以整个服务try捕获NoSuchProcess：任一子进程瞬时退出可能跳过其他子进程的清理。现版本149–191行对每个子进程身份、命令、信号及末尾检查独立捕获并继续，保留其余已记录PID/create_time核验与清理；最外捕获只标明owner在子树快照前已退出。此项已闭合，原发现保存在JSON。

只向记录owner的后代发送信号，身份不符不发信号；剩余同身份存活子进程会报错。端口预检及关闭检查不能单独证明所有可能的worker已退出；若owner在子树快照前已消失，工具明确记录这一边界，此时仍应使用已有全部owner身份验证记录核对，不把“owner已退出”升级成已枚举所有后代。

本次真实中断已另存RUN4根`RESOURCE_STOP_01.json/md`：90%守卫事实、23阶段DIVE成功、18阶段CNC采集成功、drone2/engine16阶段失败及未运行scope保持原样。后续resume01继续用户目标，不覆盖本次中断证据。没有修改旧RUN3审查或旧封存包。
