# Neocontrol Module Manager

Home Assistant App experimental para a família cabeada **Neocontrol Module Classic**.

O App conversa diretamente com os módulos pela rede local usando UDP/IPv4 na porta 8760, oferece uma interface via Ingress e publica botões de cenas por MQTT Discovery quando um broker MQTT está disponível. Ele não usa HACS, Node-RED ou cloud Neocontrol.

## Estado

Versão inicial: `0.1.0-alpha.1` (`experimental`). O protocolo de cenas e a estrutura do frame individual são implementados conforme o handoff. Os campos `function`/`subfunction` continuam experimentais e não são inferidos automaticamente.

## Instalação no Home Assistant

1. Abra o repositório publicado: https://github.com/aoliveira07/home-assistant-neocontrol-module-manager
2. Em **Settings → Apps → App Store → Repositories**, adicione `https://github.com/aoliveira07/home-assistant-neocontrol-module-manager`.
3. Instale **Neocontrol Module Manager**.
4. Inicie o App e abra-o pelo painel lateral via Ingress.

O App usa `host_network: true` para permitir broadcast UDP. O MQTT é declarado como `want`: sem broker disponível, a interface, o listener e o Protocol Lab continuam funcionando.

## Desenvolvimento local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
$env:PYTHONPATH = "$PWD\neocontrol-module-manager"
$env:APP_DATA_DIR = "$PWD\data"
python -m app.main
```

O código da aplicação fica em `neocontrol-module-manager/app`. Para executar os testes:

```powershell
pytest
```

O App publicado usa a imagem multi-arch no GHCR. O build local usa o `Dockerfile` dentro de `neocontrol-module-manager`. O repositório não possui `build.yaml` porque o builder atual do Home Assistant não usa mais esse arquivo; o `FROM` explícito e os labels necessários estão no Dockerfile.

## Segurança do Protocol Lab

O envio individual e raw é bloqueado por padrão. Habilite o Protocol Lab na própria interface e confirme o aviso antes de enviar frames experimentais. Não há brute force, varredura automática ou descoberta ativa.

## Documentação

- [Protocolo conhecido](docs/protocol.md)
- [Documentação do App](neocontrol-module-manager/DOCS.md)
- [Changelog](neocontrol-module-manager/CHANGELOG.md)

