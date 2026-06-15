# 🏭 Fluxo Operacional: Agência MKT Guardian AI

Este documento descreve como nossa fábrica de mídia funciona, do planejamento à entrega do vídeo.

## 1. Diagrama Visual

```mermaid
graph TD
    A[📝 Início: Lista de Temas] --> B{🤖 Agente 01: Estrategista};
    B -->|Gera JSON| C[📜 Roteiro de Áudio + Prompt de Imagem];
    
    C --> D{🎨 Agente 07: Nexus Render};
    
    subgraph "Fábrica de Mídia (Nexus Render)"
        D -->|Prompt Texto| E[🧠 Gemini 2.5 Flash Image];
        E -->|Falha?| F[🖼️ Criar Imagem Conceitual (Fallback)];
        E -->|Sucesso| G[📸 Imagem Realista Gerada];
        F --> G;
        
        C -->|Texto Roteiro| H[🎙️ ElevenLabs API];
        H --> I[🔊 Áudio Neural (.mp3)];
    end
    
    G & I --> J{🎬 Montagem (MoviePy)};
    J -->|Une Imagem + Áudio + FPS| K[🎥 Vídeo Final (.mp4)];
    
    K --> L[💾 Salvar em output_videos/];
    L --> M{Mais vídeos na lista?};
    M -->|Sim| B;
    M -->|Não| N[✅ Campanha Pronta para Postagem];


