# PoliTerm Orchestrator İmplementasyon Planı

## Genel Bakış
Bu plan, Politerm Architecture.md'de tanımlanan TUI-tabanlı AI orchestrator sistemini adım adım hayata geçirmek için oluşturulmuştur. İki AI CLI TUI'yi (Planner ve Executer) tmux pane'lerinde çalıştırıp, aralarındaki iletişimi otomatikleştirecek minimal bir çalışan prototip inşa edeceğiz.

## Faz 1: Temel Altyapı ve Dizin Yapısı (✓ tamamlandığında commit)
- [ ] Proje dizin yapısını oluştur
  - [ ] `scripts/` dizini
  - [ ] `proto/` dizini
  - [ ] `config/` dizini
  - [ ] `tests/` dizini
- [ ] README.md dosyasını oluştur (mimari dokümanına referans ile)
- [ ] .gitignore dosyası oluştur
- [ ] **Git Commit**: "Initial project structure"

## Faz 2: tmux Bootstrap Script'leri (✓ tamamlandığında commit)
- [ ] `scripts/bootstrap_tmux.sh` oluştur
  - [ ] tmux session ve pane kurulumu
  - [ ] PLANNER ve EXECUTER TUI başlatma mantığı
  - [ ] Primer prompt injection desteği
  - [ ] Çevre değişkenleri ile konfigürasyon
- [ ] `scripts/kill_tmux.sh` oluştur
  - [ ] tmux session temizleme
- [ ] Script'leri çalıştırılabilir yap (chmod +x)
- [ ] **Git Commit**: "Add tmux bootstrap and cleanup scripts"

## Faz 3: Konfigürasyon Dosyaları (✓ tamamlandığında commit)
- [ ] `config/poli.env` oluştur
  - [ ] PLANNER_CMD ve PLANNER_CWD
  - [ ] EXECUTER_CMD ve EXECUTER_CWD
  - [ ] tmux socket ve session değişkenleri
  - [ ] Timeout değerleri
- [ ] Primer prompt'ları için ayrı dosyalar oluştur
  - [ ] `config/planner_primer.txt`
  - [ ] `config/executer_primer.txt`
- [ ] **Git Commit**: "Add configuration files and primers"

## Faz 4: Orchestrator Engine (✓ her major fonksiyon sonrası commit)
- [ ] `proto/poli_orchestrator.py` oluştur
  - [ ] tmux kontrol fonksiyonları (send_keys, capture_tail)
  - [ ] **Git Commit**: "Add tmux control functions"
  - [ ] Tagged block parser (regex ile POLI:MSG blokları)
  - [ ] **Git Commit**: "Add message block parser"
  - [ ] Block bekleme ve timeout yönetimi
  - [ ] **Git Commit**: "Add block detection with timeout"
  - [ ] Ana routing mantığı (route_once fonksiyonu)
  - [ ] **Git Commit**: "Implement main routing logic"
  - [ ] Main entry point ve basit CLI
  - [ ] **Git Commit**: "Add CLI entry point"

## Faz 5: Test Altyapısı (✓ tamamlandığında commit)
- [ ] `tests/smoke_loop.sh` oluştur
  - [ ] Bootstrap → orchestrator → cleanup akışı
  - [ ] Başarı/başarısızlık kontrolü
- [ ] Mock TUI script'leri (claude ve codex simülatörleri)
  - [ ] `tests/mock_planner.py`
  - [ ] `tests/mock_executer.py`
- [ ] **Git Commit**: "Add test infrastructure and mock TUIs"

## Faz 6: İyileştirmeler ve Güvenilirlik (✓ her iyileştirmede commit)
- [ ] Orchestrator'a logging ekle
  - [ ] **Git Commit**: "Add logging to orchestrator"
- [ ] Interrupt handling (Ctrl-C graceful shutdown)
  - [ ] **Git Commit**: "Add interrupt handling"
- [ ] State tracking (task_id yönetimi)
  - [ ] **Git Commit**: "Improve state tracking"
- [ ] Retry mantığı ve nudge mekanizması
  - [ ] **Git Commit**: "Add retry and nudge mechanism"

## Faz 7: Dokümantasyon ve Polish (✓ tamamlandığında commit)
- [ ] README.md'yi detaylandır
  - [ ] Kurulum adımları
  - [ ] Kullanım örnekleri
  - [ ] Troubleshooting
- [ ] Inline dokümantasyon ve type hint'ler ekle
- [ ] **Git Commit**: "Complete documentation"

## Faz 8: End-to-End Test ve Validation
- [ ] Gerçek claude ve codex (veya alternatifleri) ile test
- [ ] Acceptance criteria kontrolü:
  - [ ] tmux session'ları doğru cwd'lerde başlıyor
  - [ ] Primer'lar başarıyla inject ediliyor
  - [ ] Tagged block'lar doğru parse ediliyor
  - [ ] Planner → Executer → Planner routing çalışıyor
  - [ ] Context kaybı yok
  - [ ] Timeout'lar düzgün handle ediliyor
- [ ] **Git Commit**: "Final validation and fixes"

## Git Workflow
- Her faz sonunda anlamlı commit mesajları ile commit yapılacak
- Kritik değişikliklerde ara commit'ler atılacak
- Branch stratejisi: main branch'te doğrudan çalışma (MVP için)
- Problem durumunda rollback için tag'ler kullanılacak

## Notlar
- Python 3.10+ stdlib only (MVP için harici bağımlılık yok)
- tmux 3.x+ gerekli
- macOS/Linux uyumlu
- İlk fazda sadece local çalışma (güvenlik)
- Extension'lar (ZMQ, gRPC, UI) Phase-2 için saklanacak

## Başarı Kriterleri
✅ Minimal çalışan prototip
✅ İki TUI arasında otomatik mesaj routing'i
✅ Context korunumu
✅ Temiz, okunabilir, genişletilebilir kod
✅ Comprehensive git history