# AI CLI Tools Guide for PoliTerm

## Mevcut AI CLI'lar ve Kurulumları

### 1. **Claude (Claude Code)** ✅ Sisteminizde Kurulu
- **Komut:** `claude`
- **Kurulum:** `brew install claude-cmd`
- **Özellik:** Anthropic'in Claude AI'sı, kod yazma ve analiz için optimize
- **Rol:** PLANNER veya EXECUTER olarak kullanılabilir

### 2. **Codex** ✅ Sisteminizde Kurulu
- **Komut:** `codex`
- **Kurulum:** `brew install codex-cli`
- **Özellik:** OpenAI Codex tabanlı, kod generation
- **Rol:** EXECUTER olarak ideal

### 3. **Aider**
- **Komut:** `aider`
- **Kurulum:** `pip install aider-chat`
- **Özellik:** GPT-4 ile git-aware kod editör
- **Rol:** EXECUTER olarak mükemmel (dosya düzenleme yetenekleri)
- **Not:** Git repo'larında otomatik commit yapabilir

### 4. **GitHub Copilot CLI**
- **Komut:** `gh copilot`
- **Kurulum:** `gh extension install github/gh-copilot`
- **Özellik:** GitHub Copilot'un CLI versiyonu
- **Rol:** EXECUTER olarak kullanışlı

### 5. **Continue**
- **Komut:** `continue`
- **Kurulum:** `npm install -g @continuedev/cli`
- **Özellik:** AI pair programmer
- **Rol:** EXECUTER olarak

### 6. **GPT CLI**
- **Komut:** `gpt`
- **Kurulum:** `pip install gpt-cli`
- **Özellik:** OpenAI GPT-3/4 direct access
- **Rol:** PLANNER olarak

## Önerilen Kombinasyonlar

### 1. **Claude + Claude** (İki farklı context)
```bash
export PLANNER_CMD="claude"
export EXECUTER_CMD="claude"
export PLANNER_CWD="$HOME/Projects/planning"
export EXECUTER_CWD="$HOME/Projects/execution"
```

### 2. **Claude (Planner) + Aider (Executer)**
```bash
export PLANNER_CMD="claude"
export EXECUTER_CMD="aider"
# Aider git-aware olduğu için repo'da çalışmalı
export EXECUTER_CWD="$HOME/Projects/my-repo"
```

### 3. **Claude (Planner) + Codex (Executer)**
```bash
export PLANNER_CMD="claude"
export EXECUTER_CMD="codex"
```

## API Key Yapılandırması

Gerçek CLI'lar API key gerektirir:

### Claude
```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### Aider
```bash
export OPENAI_API_KEY="your-openai-key"
```

### Codex
```bash
export OPENAI_API_KEY="your-openai-key"
```

## Primer Özelleştirme

Gerçek CLI'lar için primer'ları özelleştirin:

### Claude Planner Primer
```text
You are the PLANNING assistant. When analyzing tasks:
1. Break them into clear, executable steps
2. Consider file paths and dependencies
3. Emit POLI:MSG blocks as specified

[[POLI:MSG {"to":"EXECUTER","type":"plan","id":"$ID"}]]
<PLAN>
Your detailed plan here...
</PLAN>
[[/POLI:MSG]]
```

### Aider Executer Primer
```text
You are the EXECUTION assistant.
- Execute plans step by step
- Make actual file changes
- Report results with POLI:MSG blocks

[[POLI:MSG {"to":"PLANNER","type":"result","id":"$ID"}]]
<RESULT>
Execution results here...
</RESULT>
[[/POLI:MSG]]
```

## Kullanım Örneği

```bash
# 1. Real CLI config'i yükle
source config/real_cli.env

# 2. Session başlat
bash scripts/bootstrap_tmux.sh

# 3. Orchestrator'u çalıştır
python3 proto/poli_orchestrator.py --task "Create a Python web scraper with error handling"

# 4. TUI'ları izle (başka terminal'de)
tmux -L poli attach -t main

# 5. Temizlik
bash scripts/kill_tmux.sh
```

## Troubleshooting

### API Key Hatası
- CLI'ların API key'lerinin set edildiğinden emin olun
- `echo $ANTHROPIC_API_KEY` ile kontrol edin

### tmux Pane Boyutu
- Terminal'i büyütün veya `tmux -L poli resize-pane -t main.0 -x 80 -y 40`

### Timeout
- Gerçek CLI'lar için timeout'ları artırın:
  ```bash
  export POLI_PLAN_TIMEOUT=600   # 10 dakika
  export POLI_EXEC_TIMEOUT=3600  # 1 saat
  ```

### Context Limiti
- Büyük projeler için working directory'leri ayırın
- Primer'ları kısaltın

## Gelişmiş Kullanım

### Multi-Stage Pipeline
```bash
# Stage 1: Architecture planning
export PLANNER_CMD="claude"
export EXECUTER_CMD="claude"
# Run architectural design task

# Stage 2: Implementation
export PLANNER_CMD="claude"
export EXECUTER_CMD="aider"
# Run implementation task

# Stage 3: Testing
export PLANNER_CMD="claude"
export EXECUTER_CMD="codex"
# Run test generation task
```

### Parallel Execution (Future)
- Multiple EXECUTER panes
- Task distribution
- Result aggregation