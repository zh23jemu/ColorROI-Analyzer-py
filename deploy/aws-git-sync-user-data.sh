#!/bin/bash
# AWS EC2 首次启动脚本模板：从 GitHub public repo 拉取 ColorROI Analyzer 并运行 Streamlit。
#
# 用法：
#   1. 在 EC2 user-data 中使用本文件内容。
#   2. 根据需要调整 REPO_URL、BRANCH、APP_DIR 和 Streamlit 端口。
#   3. 实例启动后会创建 systemd 服务和定时器，每分钟尝试从 GitHub 快进拉取更新。
#
# 设计说明：
#   - 代码来源固定为 GitHub public repo，不再依赖 S3 zip 部署包。
#   - 同步脚本只使用 `git pull --ff-only`，避免覆盖服务器本地未提交修改。
#   - 每次检测到新提交后重新安装依赖并重启 Streamlit 服务。

set -euxo pipefail

exec > >(tee /var/log/colorroi-user-data.log | logger -t colorroi-user-data -s 2>/dev/console) 2>&1

REPO_URL="https://github.com/zh23jemu/ColorROI-Analyzer-py.git"
BRANCH="master"
APP_DIR="/opt/colorroi"
PYTHON_BIN="python3.11"
STREAMLIT_PORT="80"

dnf install -y git python3.11 python3.11-pip

if [ ! -d "$APP_DIR/.git" ]; then
  if [ -e "$APP_DIR" ]; then
    mv "$APP_DIR" "${APP_DIR}.backup.$(date +%Y%m%d%H%M%S)"
  fi
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
"$PYTHON_BIN" -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

cat >/etc/systemd/system/colorroi.service <<SERVICE
[Unit]
Description=ColorROI Analyzer Streamlit public test service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=PYTHONPATH=$APP_DIR/src
Environment=STREAMLIT_SERVER_HEADLESS=true
Environment=STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ExecStart=$APP_DIR/.venv/bin/python -m streamlit run $APP_DIR/app.py --server.address 0.0.0.0 --server.port $STREAMLIT_PORT --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

cat >/usr/local/bin/colorroi-git-sync.sh <<SYNC
#!/bin/bash
# 定期从 GitHub 同步代码。服务器端不产生业务修改，因此仅允许快进更新。
set -euo pipefail

APP_DIR="$APP_DIR"
BRANCH="$BRANCH"
cd "\$APP_DIR"

git fetch origin "\$BRANCH"
LOCAL_HEAD="\$(git rev-parse HEAD)"
REMOTE_HEAD="\$(git rev-parse "origin/\$BRANCH")"

if [ "\$LOCAL_HEAD" != "\$REMOTE_HEAD" ]; then
  git pull --ff-only origin "\$BRANCH"
  "\$APP_DIR/.venv/bin/python" -m pip install -r "\$APP_DIR/requirements.txt"
  systemctl restart colorroi.service
fi
SYNC

chmod +x /usr/local/bin/colorroi-git-sync.sh

cat >/etc/systemd/system/colorroi-git-sync.service <<'SERVICE'
[Unit]
Description=Sync ColorROI Analyzer code from GitHub

[Service]
Type=oneshot
ExecStart=/usr/local/bin/colorroi-git-sync.sh
SERVICE

cat >/etc/systemd/system/colorroi-git-sync.timer <<'TIMER'
[Unit]
Description=Run ColorROI Analyzer Git sync every minute

[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
AccuracySec=15s
Unit=colorroi-git-sync.service

[Install]
WantedBy=timers.target
TIMER

systemctl daemon-reload
systemctl enable --now colorroi.service
systemctl enable --now colorroi-git-sync.timer
