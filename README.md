<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MyEAP - Enterprise Equipment Automation Program</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #24292e;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .badges {
            margin-top: 20px;
            display: flex;
            justify-content: center;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .badge {
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9em;
        }
        
        .tabs {
            display: flex;
            background: #f6f8fa;
            border-bottom: 1px solid #d0d7de;
        }
        
        .tab {
            padding: 15px 30px;
            cursor: pointer;
            border: none;
            background: transparent;
            font-size: 1em;
            color: #57606a;
            transition: all 0.3s;
            border-bottom: 3px solid transparent;
        }
        
        .tab:hover {
            background: #f0f0f0;
        }
        
        .tab.active {
            color: #0969da;
            border-bottom-color: #0969da;
            font-weight: 600;
        }
        
        .content {
            padding: 40px;
            display: none;
        }
        
        .content.active {
            display: block;
        }
        
        h2 {
            color: #24292e;
            margin: 30px 0 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #d0d7de;
        }
        
        h3 {
            color: #24292e;
            margin: 20px 0 10px;
        }
        
        p {
            margin: 10px 0;
        }
        
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        
        .feature-card {
            background: #f6f8fa;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #d0d7de;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .feature-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        
        .feature-card h4 {
            color: #0969da;
            margin-bottom: 10px;
        }
        
        .feature-list {
            list-style: none;
        }
        
        .feature-list li {
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        
        .feature-list li:last-child {
            border-bottom: none;
        }
        
        .status-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        
        .status-table th, .status-table td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #d0d7de;
        }
        
        .status-table th {
            background: #f6f8fa;
            font-weight: 600;
        }
        
        .status-table tr:hover {
            background: #f6f8fa;
        }
        
        .status-done {
            color: #1a7f37;
            font-weight: 600;
        }
        
        .status-wip {
            color: #bf8700;
            font-weight: 600;
        }
        
        .code-block {
            background: #24292e;
            color: #e6edf3;
            padding: 20px;
            border-radius: 10px;
            overflow-x: auto;
            margin: 15px 0;
        }
        
        .code-block code {
            font-family: 'Fira Code', 'Consolas', monospace;
        }
        
        .quick-links {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin: 20px 0;
        }
        
        .quick-link {
            display: inline-block;
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 500;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .quick-link:hover {
            transform: translateY(-3px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        
        .footer {
            background: #24292e;
            color: #e6edf3;
            padding: 30px;
            text-align: center;
        }
        
        .footer p {
            opacity: 0.8;
        }
        
        @media (max-width: 768px) {
            .header h1 {
                font-size: 2em;
            }
            
            .tabs {
                overflow-x: auto;
            }
            
            .tab {
                padding: 12px 20px;
                white-space: nowrap;
            }
            
            .content {
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>MyEAP</h1>
            <p>Enterprise Equipment Automation Program for Semiconductor Manufacturing</p>
            <div class="badges">
                <span class="badge">🐍 Python 3.11+</span>
                <span class="badge">📦 Docker Ready</span>
                <span class="badge">☸️ Kubernetes</span>
                <span class="badge">📄 MIT License</span>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('en')">🇺🇸 English</button>
            <button class="tab" onclick="showTab('zh')">🇨🇳 中文</button>
        </div>
        
        <!-- English Content -->
        <div id="en" class="content active">
            <h2>🚀 Quick Start</h2>
            <div class="code-block">
                <code>
# Clone repository
git clone https://github.com/fzrai/myeap.git
cd myeap

# Install dependencies
uv sync

# Run tests
uv run pytest

# Start development server
uv run uvicorn myeap.api.main:app --reload
                </code>
            </div>
            
            <h2>✨ Features</h2>
            <div class="feature-grid">
                <div class="feature-card">
                    <h4>SECS/GEM Protocol</h4>
                    <ul class="feature-list">
                        <li>SECS-II encoding/decoding</li>
                        <li>HSMS connection management</li>
                        <li>GEM state machine (SEMI E30)</li>
                        <li>Standard message handling</li>
                    </ul>
                </div>
                <div class="feature-card">
                    <h4>MES Integration</h4>
                    <ul class="feature-list">
                        <li>MQTT adapter</li>
                        <li>REST API gateway</li>
                        <li>Kafka consumer</li>
                        <li>Work order management</li>
                    </ul>
                </div>
                <div class="feature-card">
                    <h4>Equipment Control</h4>
                    <ul class="feature-list">
                        <li>Equipment abstraction</li>
                        <li>Chamber control</li>
                        <li>Process control</li>
                        <li>Plugin system</li>
                    </ul>
                </div>
                <div class="feature-card">
                    <h4>Recipe Management</h4>
                    <ul class="feature-list">
                        <li>Version control</li>
                        <li>Approval workflow</li>
                        <li>Upload/download</li>
                        <li>Validation rules</li>
                    </ul>
                </div>
                <div class="feature-card">
                    <h4>Alarm Management</h4>
                    <ul class="feature-list">
                        <li>Multi-level alarms</li>
                        <li>Auto-escalation</li>
                        <li>Multi-channel notifications</li>
                        <li>Statistics & analytics</li>
                    </ul>
                </div>
                <div class="feature-card">
                    <h4>Data & Quality</h4>
                    <ul class="feature-list">
                        <li>Real-time collection</li>
                        <li>SPC control charts</li>
                        <li>FDC fault detection</li>
                        <li>Traceability</li>
                    </ul>
                </div>
            </div>
            
            <h2>📊 Development Status</h2>
            <table class="status-table">
                <thead>
                    <tr>
                        <th>Module</th>
                        <th>Status</th>
                        <th>Tests</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>SECS/GEM Protocol</td>
                        <td class="status-done">✅ Done</td>
                        <td>47+</td>
                    </tr>
                    <tr>
                        <td>MES Integration</td>
                        <td class="status-done">✅ Done</td>
                        <td>81+</td>
                    </tr>
                    <tr>
                        <td>Device Control</td>
                        <td class="status-done">✅ Done</td>
                        <td>75+</td>
                    </tr>
                    <tr>
                        <td>Recipe Management</td>
                        <td class="status-done">✅ Done</td>
                        <td>105+</td>
                    </tr>
                    <tr>
                        <td>Alarm Management</td>
                        <td class="status-done">✅ Done</td>
                        <td>71+</td>
                    </tr>
                    <tr>
                        <td>Data Collection</td>
                        <td class="status-done">✅ Done</td>
                        <td>84+</td>
                    </tr>
                    <tr>
                        <td>Tracking Service</td>
                        <td class="status-done">✅ Done</td>
                        <td>62+</td>
                    </tr>
                    <tr>
                        <td>SPC/FDC Engine</td>
                        <td class="status-wip">🔄 WIP</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>AI/ML Module</td>
                        <td class="status-wip">🔄 WIP</td>
                        <td>-</td>
                    </tr>
                </tbody>
            </table>
            
            <h2>📚 Documentation</h2>
            <div class="quick-links">
                <a href="README_en.md" class="quick-link">📖 Full English Docs</a>
                <a href="docs/" class="quick-link">📋 API Reference</a>
                <a href="https://github.com/fzrai/myeap" class="quick-link">⭐ GitHub</a>
            </div>
        </div>
        
        <!-- Chinese Content -->
        <div id="zh" class="content">
            <h2>🚀 快速开始</h2>
            <div class="code-block">
                <code>
# 克隆仓库
git clone https://github.com/fzrai/myeap.git
cd myeap

# 安装依赖
uv sync

# 运行测试
uv run pytest

# 启动开发服务器
uv run uvicorn myeap.api.main:app --reload
                </code>
            </div>
            
            <h2>✨ 核心功能</h2>
            <div class="feature-grid">
                <div class="feature-card">
                    <h4>SECS/GEM协议</h4>
                    <ul class="feature-list">
                        <li>SECS-II消息编解码</li>
                        <li>HSMS连接管理</li>
                        <li>GEM状态机 (SEMI E30)</li>
                        <li>标准消息处理</li>
                    </ul>
                </div>
                <div class="feature-card">
                    <h4>MES集成</h4>
                    <ul class="feature-list">
                        <li>MQTT适配器</li>
                        <li>REST API网关</li>
                        <li>Kafka消费者</li>
                        <li>工单管理</li>
                    </ul>
                </div>
                <div class="feature-card">
                    <h4>设备控制</h4>
                    <ul class="feature-list">
                        <li>设备抽象</li>
                        <li>腔体控制</li>
                        <li>工艺控制</li>
                        <li>插件系统</li>
                    </ul>
                </div>
                <div class="feature-card">
                    <h4>配方管理</h4>
                    <ul class="feature-list">
                        <li>版本控制</li>
                        <li>审批流程</li>
                        <li>上传下载</li>
                        <li>验证规则</li>
                    </ul>
                </div>
                <div class="feature-card">
                    <h4>报警管理</h4>
                    <ul class="feature-list">
                        <li>多级报警</li>
                        <li>自动升级</li>
                        <li>多渠道通知</li>
                        <li>统计与分析</li>
                    </ul>
                </div>
                <div class="feature-card">
                    <h4>数据与质量</h4>
                    <ul class="feature-list">
                        <li>实时采集</li>
                        <li>SPC控制图</li>
                        <li>FDC故障检测</li>
                        <li>追踪追溯</li>
                    </ul>
                </div>
            </div>
            
            <h2>📊 开发状态</h2>
            <table class="status-table">
                <thead>
                    <tr>
                        <th>模块</th>
                        <th>状态</th>
                        <th>测试</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>SECS/GEM协议</td>
                        <td class="status-done">✅ 已完成</td>
                        <td>47+</td>
                    </tr>
                    <tr>
                        <td>MES集成</td>
                        <td class="status-done">✅ 已完成</td>
                        <td>81+</td>
                    </tr>
                    <tr>
                        <td>设备控制</td>
                        <td class="status-done">✅ 已完成</td>
                        <td>75+</td>
                    </tr>
                    <tr>
                        <td>配方管理</td>
                        <td class="status-done">✅ 已完成</td>
                        <td>105+</td>
                    </tr>
                    <tr>
                        <td>报警管理</td>
                        <td class="status-done">✅ 已完成</td>
                        <td>71+</td>
                    </tr>
                    <tr>
                        <td>数据采集</td>
                        <td class="status-done">✅ 已完成</td>
                        <td>84+</td>
                    </tr>
                    <tr>
                        <td>追踪服务</td>
                        <td class="status-done">✅ 已完成</td>
                        <td>62+</td>
                    </tr>
                    <tr>
                        <td>SPC/FDC引擎</td>
                        <td class="status-wip">🔄 开发中</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>AI/ML模块</td>
                        <td class="status-wip">🔄 开发中</td>
                        <td>-</td>
                    </tr>
                </tbody>
            </table>
            
            <h2>📚 文档资料</h2>
            <div class="quick-links">
                <a href="README_zh.md" class="quick-link">📖 完整中文文档</a>
                <a href="docs/" class="quick-link">📋 API参考</a>
                <a href="https://github.com/fzrai/myeap" class="quick-link">⭐ GitHub</a>
            </div>
        </div>
        
        <div class="footer">
            <p>Made with ❤️ for Semiconductor Manufacturing | 为半导体制造而生</p>
            <p style="margin-top: 10px;">MIT License | 2024</p>
        </div>
    </div>
    
    <script>
        function showTab(tab) {
            // Hide all content
            document.querySelectorAll('.content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            
            // Show selected tab
            document.getElementById(tab).classList.add('active');
            event.target.classList.add('active');
        }
    </script>
</body>
</html>
