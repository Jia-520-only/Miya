# ========================================
#  Miya CI/CD 本地检查
#  模拟 GitHub Actions 的 CI 流程
#  用法: make ci
# ========================================

.PHONY: ci quality lint test security test-all format fix help

# 默认：运行所有 CI 检查
ci: quality test-all security
	@echo ""
	@echo "===== CI 检查全部完成 ====="

# 代码质量检查
quality: lint
	@echo "[2/3] ruff format check..."
	python -m ruff format --check .

# Lint 检查
lint:
	@echo "[1/3] ruff check..."
	python -m ruff check .

# 安全审计
security:
	@echo "[3/3] bandit security audit..."
	@python -m bandit --version >/dev/null 2>&1 || (echo "bandit 未安装，无法执行安全审计。安装: pip install bandit" && exit 1)
	python -m bandit -c .bandit -r core hub run -ll

# 全部测试（e2e + integration）
test-all:
	@echo "运行所有测试..."
	python -m pytest tests/ -v --tb=short --timeout=60

# 单元测试（如 tests/unit/ 存在）
test:
	@if [ -d "tests/unit" ]; then \
		python -m pytest tests/unit/ -v --tb=short --timeout=60; \
	else \
		echo "tests/unit/ 目录不存在，运行所有可用测试..."; \
		python -m pytest tests/ -v --tb=short --timeout=60; \
	fi

# 自动修复格式问题
fix:
	python -m ruff check --fix .
	python -m ruff format .

# 格式化代码（不检查）
format:
	python -m ruff format .



# 帮助
help:
	@echo "make ci       - 运行完整 CI 检查"
	@echo "make quality  - 代码质量检查（ruff）"
	@echo "make lint     - 代码风格检查（ruff check）"
	@echo "make security - 安全审计（bandit）"
	@echo "make format   - 格式化代码"
	@echo "make test     - 运行测试"
	@echo "make test-all - 运行所有测试"
	@echo "make fix      - 自动修复格式问题"
