# 🎬 Movie Player Lite

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [Español](README.es.md) | **Português** | [Deutsch](README.de.md)

Um reprodutor de vídeo gratuito para Windows que permite **recortar só o trecho que você precisa, na hora e sem perder qualidade**.

---

## ⬇️ Baixar e instalar

### 👉 [Baixar o instalador do Movie Player Lite (Windows 10 / 11)](https://github.com/iseohyun/movie-player-lite/releases/latest/download/MoviePlayerLite-Setup.exe)

1. **Clique no link acima.** Um arquivo chamado `MoviePlayerLite-Setup.exe` será baixado.
2. **Dê um clique duplo no arquivo baixado.** Normalmente ele fica na pasta `Downloads`.
3. Se aparecer uma janela azul **"O Windows protegeu o computador"**, clique em **Mais informações** → **Executar assim mesmo**.
   O Windows mostra esse aviso para programas feitos por pessoas físicas; não significa que há algo errado com o programa.
4. Escolha o idioma e vá clicando em **Avançar**. Você pode deixar as opções como estão.

   | Opção | O que faz |
   | :--- | :--- |
   | Pasta de instalação | Deixe como está, a não ser que precise de outro local. |
   | Criar um atalho na área de trabalho | Marque se quiser um ícone na área de trabalho. |
   | Tipos de arquivo reproduzidos por padrão | Os tipos marcados (como `.mp4`) abrem neste programa com um clique duplo. |
   | Baixar o FFmpeg mais recente | **Deixe marcada.** Baixa o componente necessário para cortar e para salvar vídeos do YouTube. Se você já tiver, esta opção não aparece. |

5. Clique em **Instalar**, aguarde e depois clique em **Concluir**. O programa será iniciado.

- Não é preciso ter direitos de administrador. Funciona no Windows 10 / 11 de 64 bits.
- **Para remover**, abra `Configurações` → `Aplicativos` → `Aplicativos instalados` no Windows, encontre **Movie Player Lite** e clique em `Desinstalar`.

---

## 🎞️ O que você pode fazer

- **Corte ultrarrápido sem perda de qualidade** — nada é recodificado, então até vídeos longos levam segundos.
- **Girar ou inverter a imagem e salvar**, **salvar o quadro atual como captura de tela**
- **Desenhar sobre o vídeo** — os traços somem depois de um instante; ótimo para explicar algo.
- **Reproduzir a partir de um endereço do YouTube** — na primeira vez é transmitido na hora; depois, o arquivo salvo é reproduzido.
- **Velocidade de reprodução, zoom e movimento, avanço quadro a quadro, lista de reprodução**
- **Seis idiomas** — 한국어, English, 简体中文, Español, Português, Deutsch

---

## 🚀 Primeiros passos

**Abrir um vídeo**
Arraste um arquivo de vídeo para a janela do programa. Ou clique com o botão direito na imagem e escolha `Arquivo` → `Abrir`.

**Cortar o trecho desejado**
1. Pressione `E` para abrir a janela de edição.
2. Arraste as **duas linhas verdes** na linha do tempo, na parte de baixo, para definir o início e o fim.
3. Clique em **Cortar**. O original não é alterado e um novo arquivo é criado.

**Assistir a um vídeo do YouTube**
Pressione `Ctrl + U` e cole o endereço do YouTube. Use apenas com vídeos que você tem o direito de assistir.

**Mostrar o menu**
Pressione `Alt` ou clique com o botão direito na imagem. Os atalhos aparecem à direita de cada item do menu.

---

## ⌨️ Atalhos mais usados

| Função | Atalho |
| :--- | :---: |
| Reproduzir / Pausar | `Space` |
| Voltar / avançar 1 segundo | `←` / `→` |
| Voltar / avançar 5 segundos | `Shift + ←` / `Shift + →` |
| Voltar / avançar um quadro | `<` / `>` |
| Aumentar / diminuir volume | `↑` / `↓` |
| Sem áudio | `M` |
| Mais rápido / mais lento / velocidade normal | `+` / `-` / `0` |
| Tela cheia / sair | `F` / `Esc` |
| Janela de edição (corte) | `E` |
| Lista de reprodução | `L` |
| Abrir um endereço do YouTube | `Ctrl + U` |
| Girar (direita / esquerda) | `]` / `[` |
| Ampliar / reduzir / redefinir | `Ctrl + +` / `Ctrl + -` / `Ctrl + 0` |
| Salvar vídeo girado · captura de tela | `Ctrl + S` |
| Desenho ligado/desligado / apagar tudo | `D` / `C` |
| Vídeo anterior / próximo | `PgUp` / `PgDown` |
| Sobre | `F1` |

Todos os atalhos podem ser pesquisados e alterados em `Configurações` → `Atalhos`.

---

## 🌐 Mudar o idioma

Escolha em `Configurações` → `Idioma`. O programa reinicia e aplica na hora. No início ele segue o idioma do Windows.

---

## ❓ Perguntas frequentes

**Aparece a janela "O Windows protegeu o computador".**
O Windows mostra esse aviso para programas que não são assinados com um certificado pago. Clique em **Mais informações** → **Executar assim mesmo** para instalar.

**O que é o FFmpeg? Eu preciso dele?**
É uma ferramenta gratuita que corta e junta vídeos. Sem ela você ainda consegue reproduzir vídeos, mas o corte e o salvamento de vídeos do YouTube não funcionam. Deixe a opção marcada durante a instalação e ele é baixado automaticamente.

**Um vídeo do YouTube não abre.**
Isso pode acontecer por um tempo quando o YouTube muda o site. Baixe o instalador mais recente pelo link acima e instale de novo.

**Onde ficam os vídeos do YouTube salvos?**
Na pasta `%APPDATA%\MP4-Trim\youtube_cache`. Cole esse caminho na barra de endereços do Explorador de Arquivos para abrir. Apague arquivos de lá se ocupar espaço demais.

**Se eu desinstalar o programa, meus vídeos são apagados?**
Não. Só o programa é removido; seus arquivos de vídeo e os trechos que você cortou continuam onde estão.

---

## 🛠️ Para desenvolvedores

<details>
<summary>Executar e compilar a partir do código-fonte</summary>

Você precisa de: Python 3.12, `pip install PyQt6 yt-dlp pyinstaller` e FFmpeg no PATH

```
python movie-player-lite.py      executar a partir do código-fonte
.\run-dev.bat                    fechar o app em execução -> recompilar -> iniciar
.\build-installer.bat            gerar o instalador (requer Inno Setup 6)
```

- O instalador é gerado em `installer_output\MoviePlayerLite-Setup.exe`. Envie-o para uma release do GitHub com esse mesmo nome e o link de download deste documento apontará para a versão mais recente.
- A versão mostrada pelo instalador é lida da primeira entrada de `VERSION.md`.
- **Adicionar um idioma**: copie `locales/en-US.json` para `locales/<código-do-idioma>.json`, traduza, coloque o nome de exibição em `_meta.name` e ele aparece no menu automaticamente.

```
src/core/       lógica principal (corte e metadados, atalhos, i18n, YouTube)
src/ui/         interface (janela principal, reprodutor e linha do tempo, diálogos)
locales/        arquivos de tradução por idioma
installer.iss   script do instalador
```

</details>

---

## 📜 Licença e histórico

- Licença: [GPL v3](LICENSE). Pressione `F1` no programa para ver os softwares de código aberto utilizados.
- Histórico de alterações: [VERSION.md](VERSION.md)
