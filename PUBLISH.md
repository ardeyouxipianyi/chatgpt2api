# 改版发布说明

这份说明面向第一次发布 GitHub 改版项目的人。

## 1. 先创建自己的 GitHub 仓库

推荐做法是先 Fork 原项目：

1. 打开 <https://github.com/basketikun/chatgpt2api>
2. 点击右上角 `Fork`
3. Fork 到你自己的 GitHub 账号下

假设你的 GitHub 用户名是 `yourname`，Fork 后地址类似：

```text
https://github.com/yourname/chatgpt2api
```

## 2. 修改本地仓库推送地址

当前本地仓库如果还指向原项目地址，就不要直接推送。

在项目目录执行：

```bash
git remote set-url origin https://github.com/yourname/chatgpt2api.git
git remote -v
```

确认输出里的 `origin` 已经是你的仓库。

## 3. 提交代码

发布前先确认不要提交真实数据：

```bash
git status --short
```

不要提交这些内容：

```text
data/
.env
.env.local
真实账号 token
真实密钥
真实数据库文件
```

如果仓库里有 `config.json`，发布前打开看一眼，确保里面只有示例值，没有真实账号、真实 token、真实密钥。

确认无误后提交：

```bash
git add .
git commit -m "Add canvas workflow and multi-user image features"
```

## 4. 推送到 GitHub

```bash
git push -u origin main
```

推送成功后，你的改版源码就发布到 GitHub 了。

## 5. 给别人使用

### Docker 使用

服务器上准备好 `config.json`，至少要有：

```json
{
  "auth-key": "请换成你的管理员密钥"
}
```

然后启动：

```bash
docker compose up -d
```

访问地址：

```text
网页：http://服务器IP:3000
OpenAI 兼容接口：http://服务器IP:3000/v1
```

Cherry Studio 里填写：

```text
Base URL: http://服务器IP:3000/v1
API Key: 管理员密钥或用户密钥
```

### 本地开发使用

后端：

```bash
py -3.13 main.py
```

前端统一入口：

```bash
cd web
npm run dev
```

开发时仍然使用：

```text
网页：http://localhost:3000
OpenAI 兼容接口：http://localhost:3000/v1
```

内部会自动把网页请求交给 Next，把 `/v1` 和 `/api` 交给后端。

## 6. 发布前检查

建议每次发布前跑：

```bash
cd web
npx tsc --noEmit
npm run build
```

回到项目根目录再跑：

```bash
py -3.13 -m unittest test.test_image_canvas_service test.test_image_reverse_prompt test.test_image_input_compat
```

## 7. 重要提醒

- 保留原项目 LICENSE。
- README 中说明这是基于原项目的改版。
- 不要提交 `data/`，里面可能有账号、日志、图片和用户数据。
- 不要把真实 `config.json` 发到公开仓库。
- 公网部署时建议只开放 `3000` 端口。
