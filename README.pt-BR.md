# 🎬 Movie Player Lite

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | **Português** | [Deutsch](README.de.md)

## 📌 Visão geral e objetivo
- O **Movie Player Lite** é um reprodutor e divisor de vídeo sem perdas ultrarrápido que evita a perda de tempo e de qualidade causada pela recodificação da linha do tempo ao editar vídeos grandes de alta qualidade.
- Seu **corte sem perdas (stream copy) baseado em FFmpeg** extrai instantaneamente apenas o trecho necessário, sem perda de qualidade.

---

## 🔥 Principais recursos e uso

### 1. Reprodutor integrado e controle deslizante da linha do tempo
- **Reprodutor de vídeo integrado**: baseado em QMediaPlayer; reproduzir/pausar/tela cheia com clique, clique duplo ou a sobreposição do mouse
- **Linha do tempo com miniaturas de 10 cenas extraídas de forma assíncrona**: uma tira de quadros que mostra o vídeo inteiro de relance
- **Marcadores inteligentes de linha vertical de 1px**: início/fim do corte (linhas verdes de 1px) e a posição atual (linha vermelha de 1px) são sempre desenhados por cima
- **Pausa inteligente**: ao segurar ou arrastar a barra de progresso durante a reprodução, o vídeo pausa automaticamente para um controle preciso

### 2. Barras laterais de opções, histórico e lista de reprodução
- **Painel de opções à esquerda (`[`)**: sem áudio, copiar propriedades de captura, numeração automática e escolha do caminho de salvamento (mesma pasta / output / personalizada)
- **Painel de atalhos personalizados (`⌨`)**: altere e salve você mesmo os atalhos principal e secundário (`hotkeys.json`)
- **Painel da lista de reprodução à direita (`]`)**: gerencie os vídeos recentes, adicione arquivos ou arraste e solte, remova itens com Delete ou limpe tudo, com limpeza automática de arquivos ausentes (`playlist_history.json`)
- **Animação de deslizamento suave**: abertura e fechamento otimizados das barras laterais ao pressionar um atalho

---

## ⌨️ Atalhos padrão

| Função | Principal (Primary) | Secundário (Secondary) |
| :--- | :---: | :---: |
| **Alternar painel de opções** | `[` | - |
| **Alternar lista de reprodução** | `]` | - |
| **Reproduzir / Pausar** | `Space` | `K` |
| **Voltar / avançar 1 segundo** | `Left` / `Right` | `J` / `L` |
| **Voltar / avançar 5 segundos** | `Shift + Left` / `Shift + Right` | - |
| **Voltar / avançar 1 quadro** | `Ctrl + Left` / `Ctrl + Right` | - |
| **Alternar / sair da tela cheia** | `F` (ou `F11`) | `Esc` |
| **Ver detalhes do vídeo** | `?` (Shift + `/`) | - |
| **Remover item da lista** | `Delete` | - |

---

## 🌐 Idioma
- Em **Configurações → Idioma**, escolha `Idioma do sistema` (padrão) ou qualquer idioma instalado. A alteração é aplicada **após reiniciar o programa**.
- Idiomas incluídos: 한국어, English, 简体中文, Español, Português (Brasil), Deutsch. Se não houver tradução para o idioma do sistema, o inglês é usado.
- **Adicionar um idioma**: copie `locales/en-US.json` para `locales/<código-do-idioma>.json` (por exemplo `fr-FR.json`), traduza os valores, coloque o nome de exibição em `_meta.name` e mantenha a pasta `locales` ao lado do executável. Ele aparece no menu automaticamente.

---

## 📁 Estrutura do projeto

```
mp4-trim
├ src/
│  ├ core/                  # Lógica principal (corte com FFmpeg, extração de metadados/propriedades, atalhos personalizados, i18n)
│  ├ ui/                    # Componentes de UI e diálogos
│  │  ├ widgets/            # Linha do tempo, reprodutor de vídeo e campo de tempo personalizados
│  │  ├ dialogs/            # Diálogo de atribuição de atalhos
│  │  └ main_window.py      # Layout da janela principal VideoCutterApp e ligação de eventos
│  └ utils/                 # Janela de registro de exceções e utilitários de formato de tempo
├ locales/              : Arquivos de tradução por idioma (ko-KR.json, en-US.json, ...)
├ icon.ico              : Ícone principal do programa
├ MP4-Trim image.png    : Captura de tela do README
├ build.bat             : Script de build independente (versão leve / pacote completo)
├ mp4-trim.py           : Ponto de entrada (Main Entry Point)
├ README.md             : Guia de uso e informações do projeto
└ .gitignore            : Regras de exclusão do Git
```

---

## 🛠️ Preparar o FFmpeg (obrigatório)
1. **Baixar o FFmpeg**: [site oficial da Gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
2. Extraia `ffmpeg-release-essentials.zip` e copie `bin/ffmpeg.exe` para a pasta deste projeto, ou adicione-o ao **PATH** do sistema.

---

## 📜 Histórico de versões

- **v1.0.5**
  - Marcadores da linha do tempo sempre no topo do eixo Z (pontos de corte verdes de 1px / linha vermelha do cursor de 1px)
  - Pausa automática ao manipular a barra de progresso
  - Sistema de atalhos personalizados (Primary / Secondary) integrado ao `hotkeys.json`
  - Movimento preciso de 1 quadro com `Ctrl + ← / →`
  - A tecla `?` mostra as propriedades detalhadas do vídeo
  - Corrigido um erro de liberação de memória C++ na animação da barra lateral
- **v1.0.4**
  - Janela de registro de exceções para builds do PyInstaller (`sys.excepthook`)
  - Animação de deslizamento das barras laterais (`[` / `]`)
  - Limpeza automática de itens excluídos ou ausentes do histórico da lista
- **v1.0.3**
  - Reprodutor de vídeo integrado (QMediaPlayer) e controles sobrepostos ao passar o mouse
  - Linha do tempo de miniaturas (10 cenas extraídas de forma assíncrona com FFmpeg)
  - Lista de reprodução lateral (atalho `]`) com gerenciamento de histórico
- **v1.0.2**
  - Enter no campo do nome de saída executa o corte; nomes duplicados são destacados com uma borda
- **v1.0.1**
  - Corrigidos erros do histórico de tarefas e da normalização de caminhos
- **v1.0.0**
  - Primeira versão (recursos básicos do divisor de vídeo sem perdas ultrarrápido)
