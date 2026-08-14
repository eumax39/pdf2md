# Melhorias operacionais - PDF2MD 2.0.0

Esta build mantém o pipeline de conversão e o empacotamento existentes e acrescenta recursos de robustez operacional.

## Implementado

- Logs rotativos (`pdf2md.log` + backups), sem registrar o conteúdo extraído dos documentos.
- Tela **Sobre / Diagnóstico** com versão, ambiente, caminhos, componentes e health check.
- Botão para copiar diagnóstico e abrir a pasta de logs.
- Crash report local para exceções não tratadas.
- Status individual interno por arquivo: aguardando, processando, concluído, aviso, erro e cancelado.
- Retentativa automática de OCR em modo leve para timeout, erro ou resposta vazia.
- Verificação de integridade por contagem de páginas esperadas x processadas.
- Relatório final com arquivos, páginas, OCR, texto nativo, referências, alertas e tempo total.
- Manifesto local `conversao_pdf2md.json` com metadados técnicos do lote.
- Modo de compatibilidade opcional em Configurações, reduzindo a pressão da fila e o DPI de retentativa OCR.
- Cancelamento com atualização de estado dos itens ainda pendentes.
- Health check inicial e diagnóstico sob demanda.

## Não alterado nesta build

- `requirements.txt`
- `PDF2MD_V2.spec`
- dependências/DLLs do empacotamento
- arquitetura principal de OCR/conversão
- estrutura do preview PDF estabilizada na V4.3
- sistema de atualização automática preparado anteriormente para a versão 2.0.0

## Próximos upgrades recomendados

- Retomada persistente de lote interrompido.
- Cache persistente de conversões repetidas.
- Canal Beta/Estável do updater.
- Assinatura digital do instalador/executável.
- Fase C de higienização/normalização do Markdown.
