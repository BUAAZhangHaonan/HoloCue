# Viser 1.1.1 本地透明度补丁交付说明

本交付使用 **Viser 1.1.1 加本地补丁**，不是上游新版本。补丁仅在
`client/src/HDRJPGEnvironment.tsx` 第二次 HDR 纹理加载完成的分支增加：

```tsx
gl.domElement.style.opacity = "1";
```

原分支只把渐变进度设为 1，后续逐帧回调直接返回，可能把画布停在首次渐变的
中间透明度。首次渐变一帧为 `.24`；此时第二张纹理完成，旧实现会保持 `.24`。
补丁保留首载渐变，不改变 HDR 图像、光照、相机、模型、场景资产或渲染参数。

重新创建 Python 环境、重新安装或升级 Viser 后，**需要重新核对并应用补丁**。
仅安装 `viser==1.1.1` 不包含此次本地修改。不要将本补丁直接套用到源码哈希不同
的版本。HoloCue 应用源码摘要仍为
`c33e1ae4cdd7251c217e61caa31a2d58668984b0db6653d1fe4ac29929862e2a`；
它不覆盖虚拟环境依赖，因此必须同时保留下面的客户端 build 身份。

## 交付文件与使用方式

本说明所在目录为项目的 `.work/viser_hdr_opacity_fix/`。项目根目录在本次服务器上是
`/home/hdd3/zhanghaonan/projects/holocue`。

- `HDRJPGEnvironment.opacity.patch`：可复现的一行源码补丁，路径前缀为
  `a/client`、`b/client`；在包含 `client/` 的 Viser 副本根目录应用。
- `viser/client/src/HDRJPGEnvironment.tsx`：已修复源码。
- `viser/client/build/index.html`：本次实际构建并部署的成品，818780 字节。
- `original/`：原 TSX、`package-lock.json` 和 `index.html` 的完整备份。
- `HDRJPGEnvironment.opacity.test.ts`、`regression_old_behavior.json`、
  `regression_fixed_behavior.json`：组件回归源码和真实结果。
- `build_fix.py`、各项 `*_identity.json`：隔离准备、工具版本、锁文件和构建身份。

在匹配原哈希的新环境中，可使用交付的已构建 `index.html` 和修复 TSX，替换对应
Viser 安装目录下的两个准确文件。操作前关闭该项目的服务、核对原件、备份并记录
原/新 SHA；操作后重新启动 viewer。Viser 会在进程内缓存 HTML，单改磁盘文件
不能证明运行中的页面已更新。必须核对新浏览器实际收到的主文档 SHA。

如需重新构建，在独立目录复制原 client 及所需的同级 `_assets`，使用明确的
Node **24.12.0**、npm **11.6.2** 和项目内 npm 缓存。保持原 lockfile，运行
`npm ci --no-audit --no-fund`，不要用 `npm install` 更新锁文件。将回归测试放入
`client/src/`，先运行原实现测试，再应用补丁、运行修复测试，最后运行
`npm run build -- --base ./`。本次测试实际使用：

```text
node node_modules/vitest/vitest.mjs run src/HDRJPGEnvironment.opacity.test.ts --maxWorkers 1 --reporter=json --outputFile <独立结果文件>
```

上述安装、测试、构建实际均通过原 `record.py` 和资源守卫记录，RSS 上限 8 GiB，
主机最大已用比例 `.90`；原与修复测试输出分开保存。`build_fix.py` 的 action 为
prepare/node/dependencies/test-old/test-fixed/build，限定本次目录并拒绝覆盖已有
准备/身份文件，不能把它当作可以在当前已部署环境中反复运行的安装器。源码补丁
在两个测试阶段之间应用。新环境复现应使用独立目录和新记录名，并核对产物哈希。

## 实际验证与范围

组件测试使用真实 React/Three.js 和实际 HDR 组件，控制加载回调及帧时序；模拟
图形 hooks 和上下文，不渲染 WebGL。旧实现：首载 `.05 → .24 → 1` 通过，第二
纹理在一帧后到达的用例明确失败 `expected 0.24 to be 1`。一行修复后 **2/2 通过**；
TypeScript 与 Vite 生产构建 rc0。首次测试因无关 UI 样式导入而未执行用例，相关
失败记录仍保留，不计入行为验证。原锁中 jsdom 30.0.1 对 Node 24.12.0 发出 engine
警告（其声明的 Node 24 最低版本为 24.15.0）；没有因此换版本或修改依赖，实际
两项测试和构建均完成。完整记录说明见同目录 `REVIEW.md`。

部署与运行证据位于 `runs/simulation/cloud_finish90_20260921_e67b574/`：

- `shutdown_resume01_client_fix_command/execution.json` rc0；
  `service_shutdown_resume01.json` 的三服务剩余 owned 进程列表均为空，端口检查保留在
  `shutdown_gpu_ports_resume01.json`。
- `install_visor_opacity_fix_command/execution.json` rc0；
  `viser_opacity_install.json` 记录两个原 SHA 与安装后 SHA。安装器绑定本 RUN、准确
  source/target/backup 路径，先预读并核验固定 SHA，写后再比对固定 SHA；此前路径
  范围 P2 已修正并只读复核。没有运行第二次安装。
- 新服务 generation 为 `resume02`；viewer 记录器 owner PID 2037111、create_time
  1790009830.29，身份在 `viewer_resume02_repair_process.json`。readiness 最终三服务
  均 HTTP 200；这只证明就绪，不替代工作流验收。
- `hdr_display_diagnostic_after_command/execution.json` rc0；
  `hdr_diagnostic_after/diagnostic.json` 的实际 served SHA 为下表新 build SHA，画布
  最终 opacity 为 1，`browser_errors=[]`，session 为
  `93f0b4432f2348f796451c62ab339a90`。时间线保留首载 `.05/.24/.43/.62/1`。

部署前一次被动 DOM 诊断最终也达到 1，未复现永久 `.24`。旧 connector 漂白图像
的像素关系支持根因推断；确定的代码缺陷由受控组件测试证明，不能把旧现场描述为
已经通过 DOM 捕获了永久卡住。新 connector 介绍图已由独立视觉审查报告正常，
但本说明编写时完整补录仍在进行；本说明不宣称完整补录或全部 native 场景已完成。

## 精确 SHA256

| 文件 / 身份 | SHA256 |
| --- | --- |
| 原 HDRJPGEnvironment.tsx | ea854f80e057ccfbba238c645b051b1f0507c89d140e9e1902f0f6a31bf830e1 |
| 修复 HDRJPGEnvironment.tsx | 5ae7030a60649863d135806cbe9a3a4750121d819d8d762e3bc97ee11028e637 |
| 原、新 package-lock.json | 2df518d57396831ac0bb1bbd736db6905bdbeb1c98f688b93503b856f6cb420e |
| package.json（未改） | 085fc9157bbd8f989b259ccce1758a520bbd797c6ae104659bec3edee89c8381 |
| 原 build/index.html | d7a86b58a884879e1e6f09382d405bb69e761afe9fc8c1fdbe5eea6a787230e7 |
| 新 build/index.html（已实际 served） | db213945693b3efd036c6d2c6c27eca2147ea7648a95938d3a8fcd218a15be2f |
| HDRJPGEnvironment.opacity.patch | cdd4d6a62f26d49377ab7c04aa4548f4f779f300ca870453c2fbab718f5e1d95 |
| HDRJPGEnvironment.opacity.test.ts | 706c0a326df5cd2907ed04123f94454a0d8aabf5f299633aa79798440016e7b9 |
| regression_old_behavior.json | 3d9a7336b4faa378819e746dbbdfd05fd26cf224900b78e1f39c02fea61f8e08 |
| regression_fixed_behavior.json | 66ea047e7bb0424a2183a8afc952faa6de4bcd7ceb6dd80f8ab0151ec5d805a1 |
| build_fix.py | 26df144dccb81abf3728a2f0c9023f21a2a7e4b9bc77ccdd6152ec1a4354d746 |
| build_identity.json | bd40430959fd8669172a48e39cc0121ab42f26e666485c7960a3af755c05fbbd |
| node-v24.12.0-linux-x64.tar.xz | bdebee276e58d0ef5448f3d5ac12c67daa963dd5e0a9bb621a53d1cefbc852fd |
| 官方 SHASUMS256.txt | 379ddb0712938bd5f318b3c6235594478e02894f03b0a82343ac9d704e254e57 |
| install_visor_opacity_fix.py（项目辅助工具目录） | b4029c0b50acba466bcb4ce3a77267f828bef55bac6e0b8a81dcfbedf0102843 |
| viser_opacity_install.json（RUN） | 46217c854e22cda813615748ad51bede66b4ced1056ecf198b264bf5a37b1219 |
| hdr_diagnostic_after/diagnostic.json（RUN） | ae8563369229cd0c7cfb193caac526bc1cae8590c108345c212512700f542626 |

说明编写与只读复核：独立代理 `/root/cloud_code_review`。本次仅补交付文档，不改变
已完成记录、应用、活动采集/制作工具或服务。
