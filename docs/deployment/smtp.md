# SMTP 邮件发送配置指南

本项目使用 SMTP 协议发送密码找回等系统邮件。代码层（`app/services/email_service.py`）基于 Python 标准库 `smtplib`，**不绑定任何邮件服务商**——只要服务商支持 SMTP，把 `.env` 中的 5 个变量填好即可使用。

## 必填环境变量

| 变量 | 说明 |
| --- | --- |
| `SMTP_HOST` | SMTP 服务器域名，如 `smtp.qq.com`、`smtp.gmail.com` |
| `SMTP_PORT` | 端口；465 配 SSL、587 配 STARTTLS |
| `SMTP_SSL` | `true` = 端口 465 隐式 SSL；`false` = 端口 587 STARTTLS |
| `SMTP_USERNAME` | 登录账号，通常是你的完整邮箱地址 |
| `SMTP_PASSWORD` | **不是邮箱登录密码**，是服务商发的「授权码 / 应用专用密码」（见下） |
| `SMTP_FROM_EMAIL` | 发件人地址，通常等于 `SMTP_USERNAME` |

## 常见服务商预设

### QQ / Foxmail

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_SSL=true
```

获取授权码：登录 QQ 邮箱 → 设置 → 账户 → 开启「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务」→ 生成 16 位授权码。该授权码用作 `SMTP_PASSWORD`，**不能填 QQ 登录密码**。

### 163 / 网易邮箱

```env
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_SSL=true
```

获取客户端授权密码：登录 163 邮箱 → 设置 → POP3/SMTP/IMAP → 开启 SMTP 服务 → 获取授权密码。

### Gmail

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SSL=false
```

需先开启「两步验证」，再到 Google 账号 → 安全 → 应用专用密码 生成 16 位密码作为 `SMTP_PASSWORD`。

### Outlook / Hotmail / Office 365

```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_SSL=false
```

普通账号可直接使用邮箱密码；启用了 MFA 的账号需在账户设置中生成应用专用密码。

### 自建 / 企业 SMTP

按运维或 IT 部门提供的 `host` / `port` / 加密方式填写：
- 端口 465 → `SMTP_SSL=true`
- 端口 587（或 25）→ `SMTP_SSL=false`，代码自动走 `STARTTLS`

## 验证配置

```bash
cd backend && python -c "from app.core.config import settings; print('smtp_enabled =', settings.smtp_enabled)"
```

`smtp_enabled` 为 `True` 表示 4 个关键变量都已填写（HOST / USERNAME / PASSWORD / FROM_EMAIL）。然后在前端触发「忘记密码」流程，观察 `backend/logs/` 下日志里是否有 `邮件发送成功`。

## 常见报错

| 报错 | 原因 |
| --- | --- |
| `SMTPAuthenticationError` | 多半是 `SMTP_PASSWORD` 用了登录密码而非授权码；或 IP 触发了风控被拒登录。 |
| `Connection unexpectedly closed` | 端口/SSL 不匹配——465 必须 `SMTP_SSL=true`，587 必须 `false`。 |
| `Sender address rejected` | `SMTP_FROM_EMAIL` 与 `SMTP_USERNAME` 不一致，或服务商不允许该发件人。 |
| 邮件发出但收件方收不到 | 落入垃圾邮件，或服务商对 PaaS/家宽 IP 限流。换信誉好的服务商或加 SPF/DKIM。 |

## 安全提示

- `SMTP_PASSWORD` 等同登录凭证，**不要提交到 git**。`.env` 已写入 `.gitignore`。
- 若曾误提交，立即在邮箱后台**作废旧授权码**并重新生成。
- 生产环境建议使用专用发件账号，不要复用个人邮箱。
