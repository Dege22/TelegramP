import requests
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from flask import Flask

# Caminho do arquivo de backup
BACKUP_FILE = 'bot_backup.bak'

# Lista de usuários autorizados
authorized_users = set()

# Dicionário para armazenar o número de consultas diárias de cada usuário
user_usage = {}

# Limite diário de consultas por usuário
DAILY_LIMIT = 90

# ID do administrador
ADMIN_ID = 5045936267


# Função para carregar os dados do arquivo de backup
def load_backup():
    global authorized_users, user_usage
    if os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, 'r', encoding='utf-8') as file:
            data = json.load(file)
            authorized_users = set(data['authorized_users'])
            user_usage = {int(k): v for k, v in data['user_usage'].items()}


# Função para salvar os dados no arquivo de backup
def save_backup():
    data = {
        'authorized_users': list(authorized_users),
        'user_usage': user_usage
    }
    with open(BACKUP_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


# Função para resetar a contagem de uso diário
def reset_daily_usage():
    global user_usage
    for user_id in user_usage:
        user_usage[user_id] = 0
    save_backup()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(
        f'{update.effective_user.first_name}, Este é um bot de consulta exclusivo para membros da Panela. Seu ID de usuário é {user_id}. '
        'Por favor, envie seu ID para @MestreSplinterOFC para ser cadastrado.'
    )


async def addid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Você não tem permissão para usar este comando.")
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "Por favor, use o comando /addid seguido do ID do usuário. Exemplo: /addid 123456789")
        return

    user_id = int(context.args[0])
    authorized_users.add(user_id)
    save_backup()
    await update.message.reply_text(f"ID {user_id} adicionado com sucesso!")


async def cpf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in authorized_users:
        await update.message.reply_text("Você não tem permissão para usar este comando.")
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "Por favor, use o comando /cpf seguido do número do CPF. Exemplo: /cpf 86914804168")
        return

    # Verificar o uso diário do usuário
    if user_id not in user_usage:
        user_usage[user_id] = 0

    if user_usage[user_id] >= DAILY_LIMIT:
        await update.message.reply_text("Você atingiu o limite diário de consultas. O limite será resetado às 00:00.")
        return

    cpf_number = context.args[0]
    url = f"http://api.dbconsultas.com/api/v1/71383fd8-cbf6-48e6-a241-ee5c0b8bfd7a/cpf/{cpf_number}"

    try:
        response = requests.get(url, timeout=10)  # Adicionei um tempo limite de 10 segundos
        response.raise_for_status()  # Verifica se a requisição teve sucesso
        data = response.json()

        # Salva a resposta em um arquivo .txt
        file_path = f"response_{cpf_number}.txt"
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

        # Envia o arquivo ao usuário
        with open(file_path, 'rb') as file:
            await update.message.reply_document(document=InputFile(file, filename=f"response_{cpf_number}.txt"))

        # Remove o arquivo após enviar
        os.remove(file_path)

        # Incrementa o contador de uso do usuário
        user_usage[user_id] += 1
        save_backup()

        # Envia mensagem com o uso restante
        remaining_usage = DAILY_LIMIT - user_usage[user_id]
        await update.message.reply_text(
            f"Você tem {remaining_usage}/{DAILY_LIMIT} consultas restantes para hoje. O limite será resetado às 00:00.")

    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"Ocorreu um erro ao consultar o CPF, formato correto : /cpf 86914804168")


def main():
    load_backup()

    app = ApplicationBuilder().token("6361700021:AAFMSDmrihkTk4koad542YklYEJNoSxUjQo").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addid", addid))
    app.add_handler(CommandHandler("cpf", cpf))

    # Configura o agendador para resetar a contagem de uso diariamente às 00:00
    scheduler = AsyncIOScheduler()
    scheduler.add_job(reset_daily_usage, trigger='cron', hour=0, minute=0)
    scheduler.start()

    # Inicializa o bot
    app.initialize()
    app.start()

    # Inicia a aplicação Flask
    flask_app = Flask(__name__)

    @flask_app.route('/')
    def index():
        return "Bot de consulta está funcionando."

    port = int(os.environ.get('PORT', 10000))
    flask_app.run(host='0.0.0.0', port=port)


if __name__ == '__main__':
    main()
