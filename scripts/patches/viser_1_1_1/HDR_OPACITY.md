# HDR 环境画布透明度修复

`viser/client/src/HDRJPGEnvironment.tsx` 保留已验证的 Viser 1.1.1 修复：
后续 HDR 纹理加载完成时，将 `gl.domElement.style.opacity` 恢复为 `"1"`。
同目录的 `HDRJPGEnvironment.opacity.test.ts` 覆盖首载渐变和第二张纹理中途到达。
`HDRJPGEnvironment.opacity.patch` 保存历史一行修改，用于核对修改范围。

本目录 README 的复制命令 `cp -a scripts/patches/viser_1_1_1/viser/. ...`
会连同相机协议文件一起复制 HDR 源码及测试。遵循该文档的固定 Node/npm、
Viser 1.1.1、原始 lockfile、项目内缓存和隔离构建要求；重新构建前需运行：

```bash
node node_modules/vitest/vitest.mjs run src/HDRJPGEnvironment.opacity.test.ts --maxWorkers 1
```

然后按 README 构建客户端，并在记录原件和文件身份后成套安装、重启本项目 viewer。
仅复制 TSX 不会更新浏览器收到的构建文件。新环境仍需核对实际浏览器响应与视觉效果。

原先通过的组件测试、构建、真实页面检查与视频保留在本地
`.work/viser_hdr_opacity_fix/`、忽略的 `docs/cloud_review/` 和已交付 ZIP 中。
本次源码格式化会改变文件摘要，不改写历史记录，也不宣称完成了新的原生视觉验收。
