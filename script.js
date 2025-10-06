// Инициализируем объект Telegram Web App
const tg = window.Telegram.WebApp;

// Расширяем Web App на всю высоту
tg.expand();

// Объект для хранения заказа
const order = {
    hotdog: 0,
    shaurma: 0
};

const prices = {
    hotdog: 150,
    shaurma: 220
};

// Функция изменения количества товара
window.changeQuantity = function(item, delta) {
    if (order[item] + delta >= 0) {
        order[item] += delta;
        document.getElementById(${item}-quantity).innerText = order[item];
    }
}

// Находим кнопку заказа
const orderBtn = document.getElementById('order-btn');

// Обработчик клика по кнопке заказа
orderBtn.addEventListener('click', () => {
    const name = document.getElementById('user_name').value;
    const phone = document.getElementById('user_phone').value;
    const comment = document.getElementById('user_comment').value;

    // Проверка, что поля заполнены
    if (name.trim() === '' || phone.trim() === '') {
        alert('Пожалуйста, введите ваше имя и номер телефона.');
        return;
    }
    
    // Проверка, что хотя бы один товар выбран
    if (order.hotdog === 0 && order.shaurma === 0) {
        alert('Пожалуйста, выберите хотя бы один товар.');
        return;
    }

    // Формируем данные для отправки боту
    const data = {
        order: order,
        prices: prices,
        name: name,
        phone: phone,
        comment: comment
    };

    // Отправляем данные в виде JSON-строки
    tg.sendData(JSON.stringify(data));
    
    // Закрываем Web App
    tg.close();
});