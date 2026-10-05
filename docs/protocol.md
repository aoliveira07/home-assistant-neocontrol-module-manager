# Protocolo Neocontrol Module Classic

Esta tabela separa fatos confirmados de hipóteses. Nenhum item `UNKNOWN` deve ser promovido sem código oficial, documentação oficial ou captura física reproduzível.

| Recurso | Estado | Evidência / observação |
|---|---|---|
| UDP IPv4 porta 8760 | CONFIRMED | Código oficial conhecido |
| Broadcast `255.255.255.255` | CONFIRMED | Código oficial conhecido |
| Frame de cena | CONFIRMED | `02 scene//240 scene%240 FF` |
| Estrutura do frame individual | CONFIRMED | `14 00 name[8] function subfunction FF` |
| Nome lógico em 8 bytes | HIGH CONFIDENCE | Código oficial e configuração do módulo |
| Encoding do nome | UNKNOWN | Não assumir ASCII/Latin-1 sem captura |
| Padding do nome | UNKNOWN | UI oferece NUL, espaço e HEX bruto |
| Relay mapping | UNKNOWN | Descobrir com captura física |
| Dimmer mapping | UNKNOWN | Descobrir com captura física |
| Switch feedback | UNKNOWN | Descobrir com captura física |
| Discovery | UNKNOWN | Capturar tráfego do NeocData |
| Status feedback | UNKNOWN | Capturar tráfego do módulo |

## Frames confirmados

Cena `n`:

```text
02 floor(n / 240) (n % 240) FF
```

Frame individual:

```text
14 00 NN NN NN NN NN NN NN NN FUNC SUB FF
```

`FUNC` e `SUB` são deliberadamente experimentais nesta versão.

## Próxima captura física

1. Testar uma cena de iluminação segura.
2. Capturar no Protocol Lab o NeocData executando Relay CH1/CH2 ON/OFF.
3. Capturar níveis de Dimmer.
4. Capturar botoeira física.
5. Capturar a localização/discovery dos módulos.

