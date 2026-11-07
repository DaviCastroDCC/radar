# Política de Privacidade – Radar Concurso

**Versão:** 2026-11-07

O Radar Concurso é um serviço gratuito que lê diários oficiais e avisa, pelo Telegram, quando
sai um concurso que combina com os filtros que você definiu. Esta política explica quais dados
pessoais tratamos, por quê e quais são os seus direitos, conforme a Lei nº 13.709/2018 (LGPD).

## 1. Quais dados tratamos

| Dado | Origem | Para quê |
|---|---|---|
| Identificador da conversa no Telegram (`chat_id`) | Telegram, quando você manda `/start` | Saber para quem enviar os alertas |
| Filtros (cargo/órgão, UF, escolaridade, salário mínimo) | Você, pelo comando `/filtro` | Escolher quais editais te interessam |
| Editais acompanhados | Você, pelo botão "Acompanhar retificações" | Avisar sobre retificações |
| Histórico de alertas enviados | Gerado pelo serviço | Não repetir alertas e medir a qualidade do serviço |
| Data e versão do aceite desta política | Gerado quando você toca em "Aceito" | Comprovar o consentimento |
| Data de desativação | Gerada quando você pausa ou bloqueia o bot | Aplicar o prazo de retenção |

**Não** coletamos seu nome, telefone, foto, localização ou o conteúdo de outras conversas.
Os dados das publicações (editais) vêm de diários oficiais públicos e não são dados seus.

## 2. Base legal e finalidade

Tratamos seus dados com base no seu **consentimento** (art. 7º, I), dado ao tocar em "Aceito"
no início da conversa, e **exclusivamente** para enviar alertas de concursos. Você pode retirar
o consentimento a qualquer momento com `/apagar`.

## 3. Compartilhamento

Seus dados **não são vendidos, alugados nem compartilhados** com terceiros para fins comerciais.
Eles transitam apenas pelos provedores necessários para o serviço funcionar:

- **Telegram**, que entrega as mensagens;
- o **provedor de nuvem** onde o serviço está hospedado.

O texto dos diários oficiais é processado por um serviço de inteligência artificial para extrair
dados dos editais. **Nenhum dado seu é enviado nesse processamento.**

## 4. Retenção e eliminação

- Guardamos seus dados enquanto você usar o serviço.
- Se você **bloquear o bot** ou usar **`/parar`**, seus dados são **apagados automaticamente
  após 180 dias** sem reativação.
- Com **`/apagar`**, tudo é apagado **na hora**, de forma definitiva.
- Filtros removidos com `/remover` são apagados, não apenas desativados.

## 5. Seus direitos (art. 18)

Pelo próprio bot, a qualquer momento:

| Direito | Como exercer |
|---|---|
| Confirmação e acesso | `/meusdados` envia um arquivo com todos os seus dados |
| Portabilidade | O mesmo arquivo, em formato aberto (JSON) |
| Correção | Remova e recrie seus filtros (`/remover`, `/filtro`) |
| Eliminação e revogação do consentimento | `/apagar` |
| Informação sobre o tratamento | `/privacidade` e este documento |

## 6. Segurança

Os dados ficam em banco de dados com acesso restrito, trafegam por conexões criptografadas e não
são registrados em logs de aplicação.

## 7. Alterações

Se esta política mudar de forma relevante, a versão acima será atualizada e o bot pedirá um
novo aceite antes de continuar enviando alertas.

## 8. Contato

Dúvidas sobre privacidade podem ser enviadas pelo contato informado no comando `/privacidade`.
