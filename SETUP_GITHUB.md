# GitHub 仓库设置指南

## 第一步：登录 GitHub

1. 打开浏览器，访问 [GitHub 登录页面](https://github.com/login)
2. 使用你的用户名 `ukck` 和密码登录

## 第二步：创建新仓库

1. 登录后，点击右上角的 `+` 号，选择 "New repository"
   - 或直接访问：https://github.com/new

2. 填写仓库信息：
   - **Repository name**: `ffmpeg-service`
   - **Description**: `FFmpeg MP3 conversion service with FastAPI`
   - **Visibility**: 选择 `Public`（推荐）或 `Private`
   - **⚠️ 重要**: 不要勾选以下选项：
     - [ ] Add a README file
     - [ ] Add .gitignore  
     - [ ] Choose a license

3. 点击 `Create repository` 按钮

## 第三步：推送代码

创建仓库后，GitHub 会显示一个页面，其中包含推送现有仓库的命令。但我们已经为你准备好了，请在终端中运行：

```bash
# 验证远程仓库已添加
git remote -v

# 推送代码（需要 GitHub 凭据）
git push -u origin main
```

### 如果推送时提示认证错误：

#### 方法一：使用 Personal Access Token（推荐）

1. 在 GitHub 中生成 Personal Access Token：
   - 访问：https://github.com/settings/tokens
   - 点击 "Generate new token" > "Generate new token (classic)"
   - 设置名称：`ffmpeg-service-token`
   - 选择权限：勾选 `repo`（完整仓库访问权限）
   - 点击 "Generate token"
   - **⚠️ 重要**：复制生成的 token（只显示一次！）

2. 推送时使用 token：
   ```bash
   # 当提示输入密码时，输入你刚才复制的 token
   git push -u origin main
   ```

#### 方法二：配置 Git 凭据

```bash
# 配置 Git 用户信息
git config --global user.name "ukck"
git config --global user.email "your-email@example.com"

# 使用凭据助手
git config --global credential.helper store
```

## 第四步：验证设置

推送成功后：

1. 访问你的仓库：https://github.com/ukck/ffmpeg-service
2. 确认所有文件都已上传
3. 检查 GitHub Actions 是否自动开始构建：
   - 点击仓库中的 "Actions" 标签
   - 应该能看到 "Build and Push Docker Image" 工作流正在运行

## 第五步：查看 Docker 镜像

构建完成后（约 5-10 分钟），你可以在以下位置查看 Docker 镜像：

- 访问：https://github.com/ukck/ffmpeg-service/packages
- 或点击仓库主页右侧的 "Packages" 链接

生成的 Docker 镜像标签将包括：
- `ghcr.io/ukck/ffmpeg-service:latest`
- `ghcr.io/ukck/ffmpeg-service:0.1.0`
- `ghcr.io/ukck/ffmpeg-service:main`（如果推送到 main 分支）

## 使用构建的 Docker 镜像

构建完成后，你可以这样使用镜像：

```bash
# 拉取镜像
docker pull ghcr.io/ukck/ffmpeg-service:latest

# 运行容器
docker run -d -p 8000:8000 ghcr.io/ukck/ffmpeg-service:latest

# 或使用 docker-compose（更新镜像引用）
# 在 docker-compose.yaml 中将 build: . 替换为：
# image: ghcr.io/ukck/ffmpeg-service:latest
```

## 故障排除

### 如果推送失败：

1. **仓库不存在**：确认已在 GitHub 创建仓库
2. **权限错误**：检查 Personal Access Token 权限
3. **网络问题**：尝试使用 SSH 而不是 HTTPS：
   ```bash
   git remote set-url origin git@github.com:ukck/ffmpeg-service.git
   ```

### 如果 GitHub Actions 失败：

1. 检查 `.github/workflows/docker-build.yml` 文件是否正确
2. 确认仓库设置中启用了 Actions
3. 查看 Actions 日志了解具体错误信息

---

**提示**：完成设置后，每次推送代码到 `main` 分支都会自动触发 Docker 镜像构建和发布。
