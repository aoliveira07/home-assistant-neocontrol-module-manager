# Neocontrol Module Manager

## Configuração

As opções do App ficam na configuração do Home Assistant. Os valores iniciais são:

- broadcast UDP: `255.255.255.255`
- porta UDP: `8760`
- buffer circular: 500 datagramas
- Protocol Lab: desabilitado
- MQTT Discovery prefix: `homeassistant`

O App usa `/data/neocontrol.db` para persistir cenas, módulos experimentais, settings e preferências.

## MQTT

O broker é obtido automaticamente pelo serviço `mqtt` do Supervisor. O App não solicita credenciais MQTT ao usuário. Quando o serviço não está disponível, o MQTT aparece como indisponível e as funções UDP continuam operacionais.

## Protocol Lab

O listener UDP começa na inicialização. Para envio individual/raw, habilite o Protocol Lab pela interface e confirme o alerta. Os envios são manuais; não existe brute force, varredura automática nem discovery ativo.

## Diagnóstico

O painel Diagnostics exporta um relatório JSON sem senha MQTT. A captura do Protocol Lab pode ser exportada como JSON ou CSV.

