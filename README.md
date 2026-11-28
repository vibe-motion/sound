# sound

Claude Code 视频音效 Skill，用于从 [Freesound](https://freesound.org) 搜索、筛选和下载 MP3 试听文件。

适用于转场、卡片入场、按钮点击、纸张滑动和碰撞等场景。必要时可用 FFmpeg 检查音效的时长、尾音和能量分布。

## 安装

在 Claude Code 中使用需要 Python 3 和可访问 Freesound 的网络。脚本仅使用 Python 标准库。克隆前，请确认当前 GitHub 账号拥有该私有仓库的访问权限。

在项目根目录运行以下命令。

```bash
git clone https://github.com/vibe-motion/sound.git .claude/skills/sound
```

## 在 Claude Code 中使用

安装后，在视频项目中直接描述要找的音效。可以参考下面两种写法。

> 用 sound 帮我找一个卡片飞入时的短 whoosh，约 0.3 秒，适合轻快的产品演示，只选 CC0，下载到 sfx/。

> 给开关切换找一个柔和、不刺耳的点击音效。先给出候选、下载量、评分人数和试听链接。

Skill 会将画面动作转成英文关键词，按声音来源、描述、时长和许可筛选候选，并用下载量与评分人数辅助判断。你可以先索取试听链接，再选定要下载的音效。

## 直接运行脚本

脚本也可独立使用。以下命令均在项目根目录执行。

```bash
S=.claude/skills/sound/scripts/sfx.py

# 搜索 CC0 音效，并显示试听链接
python3 "$S" freesound "soft whoosh" --license cc0 --urls

# 搜索纸张滑动，允许 CC0 和需要署名的 Attribution 音效
python3 "$S" freesound "paper slide" --license by -n 5

# 将占位符替换为搜索返回的 fs:ID，可一次传入多个
python3 "$S" get sfx/ "fs:<id1>" "fs:<id2>"
```

`get` 从 `~/.cache/sfx-sources/index.json` 读取搜索结果。先搜索，再用返回的 `fs:ID` 下载。

### 搜索参数

| 参数 | 作用 |
| --- | --- |
| `--license cc0` | 仅搜索 CC0 |
| `--license by` | 搜索 CC0 和 Attribution |
| `--license any` | 不过滤许可证，默认值 |
| `--urls` | 显示试听链接 |
| `-n 5` | 最多显示 5 条结果，默认 8 条 |
| `--sort relevance` | 获取相关结果后按下载量重新排序，默认方式 |
| `--sort downloads` / `rating` / `short` | 分别按下载量、评分或时长排序 |
| `--pages 3` | 从起始页抓取的页数，默认 3 页 |
| `-p 2` | 从第 2 页开始搜索，默认第 1 页 |

## 许可证与署名

每条音效的许可证可能不同。脚本支持按 CC0 或 Attribution 筛选。默认 `any` 也可能返回 BY-NC 等其他许可的音效，使用前应检查对应条目的许可要求。

对于非 CC0 音效，`get` 会输出作者署名提示。交付时请保留音效来源和许可证，并按对应条目的要求补全署名。

## 网络排查

搜索和下载使用当前终端的 HTTP/HTTPS 代理设置。遇到超时，可检查 Freesound 是否可访问，以及终端代理是否生效。

[`references/local-setup.md`](references/local-setup.md) 和 [`scripts/clash_freesound.py`](scripts/clash_freesound.py) 针对作者的 macOS / ClashX Meta 配置。辅助脚本的 `--fix` 会修改本机 Clash 配置并切换节点，仅在环境匹配且需要调整代理时使用。

## 用户评价

<img src="assets/user-review-1.png" alt="用户分享使用 sound Skill 制作小红书视频的经历" width="360" />

## 满血版 Sound Skill

完整包包含音效素材检索、程序化音频制作和混音处理三个 Skill。获取方式与安装步骤见 [B 站充电动态](https://www.bilibili.com/opus/1270901129543155716)。
