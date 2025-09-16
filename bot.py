import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from docker_client import DockerClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramDockerBot:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.allowed_users = [int(user_id) for user_id in os.getenv('ALLOWED_USERS', '').split(',') if user_id]
        self.docker_client = DockerClient()
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        
        if self.allowed_users and user_id not in self.allowed_users:
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
            
        keyboard = [
            [InlineKeyboardButton("📋 Список контейнеров", callback_data="list_containers")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("🏷️ Образы", callback_data="list_images")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="refresh")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🐳 *Docker Manager Bot*\n\n"
            "Выберите действие:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        if self.allowed_users and user_id not in self.allowed_users:
            await query.edit_message_text("❌ У вас нет доступа к этому боту.")
            return
            
        if query.data == "list_containers":
            await self.show_containers(query)
        elif query.data == "stats":
            await self.show_stats(query)
        elif query.data == "list_images":
            await self.show_images(query)
        elif query.data == "refresh":
            await self.refresh_menu(query)
        elif query.data.startswith("container_"):
            await self.handle_container_action(query)

    async def show_containers(self, query):
        """Показать список контейнеров"""
        try:
            containers = await self.docker_client.get_containers()
            
            if not containers:
                await query.edit_message_text("📋 Контейнеры не найдены")
                return
                
            message = "📋 *Список контейнеров:*\n\n"
            keyboard = []
            
            for container in containers:
                status_emoji = "🟢" if container['status'] == 'running' else "🔴"
                message += f"{status_emoji} `{container['name']}`\n"
                message += f"   Статус: {container['status']}\n"
                message += f"   Образ: {container['image']}\n\n"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"{'⏹️' if container['status'] == 'running' else '▶️'} {container['name'][:20]}",
                        callback_data=f"container_{container['id']}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="refresh")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении контейнеров: {e}")
            await query.edit_message_text("❌ Ошибка при получении списка контейнеров")

    async def show_stats(self, query):
        """Показать статистику"""
        try:
            stats = await self.docker_client.get_stats()
            
            message = "📊 *Статистика сервера:*\n\n"
            message += f"🖥️ CPU: {stats['cpu_percent']:.1f}%\n"
            message += f"💾 Память: {stats['memory_percent']:.1f}%\n"
            message += f"💿 Диск: {stats['disk_percent']:.1f}%\n"
            message += f"🌐 Контейнеры: {stats['containers']}\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await query.edit_message_text("❌ Ошибка при получении статистики")

    async def show_images(self, query):
        """Показать список образов"""
        try:
            images = await self.docker_client.get_images()
            
            if not images:
                await query.edit_message_text("🏷️ Образы не найдены")
                return
                
            message = "🏷️ *Docker образы:*\n\n"
            
            for image in images:
                message += f"`{image['name']}`\n"
                message += f"   Размер: {image['size']}\n"
                message += f"   Создан: {image['created']}\n\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении образов: {e}")
            await query.edit_message_text("❌ Ошибка при получении образов")

    async def handle_container_action(self, query):
        """Обработка действий с контейнерами"""
        container_id = query.data.split("_")[1]
        
        try:
            container_info = await self.docker_client.get_container_info(container_id)
            
            message = f"🐳 *{container_info['name']}*\n\n"
            message += f"Статус: {container_info['status']}\n"
            message += f"Образ: {container_info['image']}\n"
            message += f"Создан: {container_info['created']}\n"
            
            keyboard = []
            
            if container_info['status'] == 'running':
                keyboard.append([InlineKeyboardButton("⏹️ Остановить", callback_data=f"stop_{container_id}")])
                keyboard.append([InlineKeyboardButton("🔄 Перезапустить", callback_data=f"restart_{container_id}")])
            else:
                keyboard.append([InlineKeyboardButton("▶️ Запустить", callback_data=f"start_{container_id}")])
            
            keyboard.append([InlineKeyboardButton("📝 Логи", callback_data=f"logs_{container_id}")])
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="list_containers")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о контейнере: {e}")
            await query.edit_message_text("❌ Ошибка при получении информации о контейнере")

    async def refresh_menu(self, query):
        """Обновить главное меню"""
        keyboard = [
            [InlineKeyboardButton("📋 Список контейнеров", callback_data="list_containers")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("🏷️ Образы", callback_data="list_images")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="refresh")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🐳 *Docker Manager Bot*\n\n"
            "Выберите действие:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    def run(self):
        """Запуск бота"""
        application = Application.builder().token(self.bot_token).build()
        
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        logger.info("Бот запущен...")
        application.run_polling()

if __name__ == "__main__":
    bot = TelegramDockerBot()
    bot.run()
