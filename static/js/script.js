// Основной JavaScript файл
console.log('NewsHub loaded');

// Автоматическое скрытие сообщений через 5 секунд
document.addEventListener('DOMContentLoaded', function () {
	const messages = document.querySelectorAll('.alert');
	messages.forEach((msg) => {
		setTimeout(() => {
			msg.style.opacity = '0';
			setTimeout(() => msg.remove(), 300);
		}, 5000);
	});

	// Инициализация обработчиков
	initFavoriteButtons();
	initReactionButtons();
	initCommentHandlers();
});

// Обработка кнопок избранного
function initFavoriteButtons() {
	const favoriteButtons = document.querySelectorAll('.favorite-btn');
	favoriteButtons.forEach(btn => {
		btn.addEventListener('click', function(e) {
			e.preventDefault();
			e.stopPropagation();
			
			const articleData = {
				url: this.dataset.url,
				title: this.dataset.title,
				description: this.dataset.description,
				urlToImage: this.dataset.image,
				source: JSON.parse(this.dataset.source),
				publishedAt: this.dataset.published
			};
			
			fetch('/api/toggle-favorite/', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-CSRFToken': getCookie('csrftoken')
				},
				body: JSON.stringify(articleData)
			})
			.then(response => response.json())
			.then(data => {
				if (data.success) {
					const icon = this.querySelector('.favorite-icon');
					if (data.is_favorite) {
						icon.textContent = '⭐';
						this.title = 'Удалить из избранного';
					} else {
						icon.textContent = '☆';
						this.title = 'Добавить в избранное';
					}
				} else {
					alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
				}
			})
			.catch(error => {
				console.error('Error:', error);
				alert('Произошла ошибка при сохранении в избранное');
			});
		});
	});
}

// Обработка кнопок реакций
function initReactionButtons() {
	const reactionButtons = document.querySelectorAll('.reaction-btn');
	reactionButtons.forEach(btn => {
		btn.addEventListener('click', function(e) {
			e.preventDefault();
			e.stopPropagation();
			
			const reactionType = this.dataset.reaction;
			const articleUrl = this.dataset.url;
			
			fetch('/api/add-reaction/', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-CSRFToken': getCookie('csrftoken')
				},
				body: JSON.stringify({
					url: articleUrl,
					reaction_type: reactionType
				})
			})
			.then(response => response.json())
			.then(data => {
				if (data.success) {
					// Обновляем все кнопки реакций для этой статьи
					const articleCard = this.closest('.news-card');
					updateReactionButtons(articleCard, data.reactions_count, data.reaction_type);
				} else {
					alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
				}
			})
			.catch(error => {
				console.error('Error:', error);
				alert('Произошла ошибка при добавлении реакции');
			});
		});
	});
}

// Обновление кнопок реакций
function updateReactionButtons(articleCard, reactionsCount, userReaction) {
	const reactionButtons = articleCard.querySelectorAll('.reaction-btn');
	
	reactionButtons.forEach(btn => {
		const reactionType = btn.dataset.reaction;
		const countElement = btn.querySelector('.reaction-count');
		
		// Убираем активный класс со всех кнопок
		btn.classList.remove('active');
		
		// Если это реакция пользователя, делаем её активной
		if (userReaction === reactionType) {
			btn.classList.add('active');
		}
		
		// Обновляем счетчик
		const count = reactionsCount && reactionsCount[reactionType] ? reactionsCount[reactionType] : 0;
		if (count > 0) {
			countElement.textContent = count;
			countElement.style.display = 'inline';
		} else {
			countElement.textContent = '';
			countElement.style.display = 'none';
		}
	});
}

// Обработка комментариев
function initCommentHandlers() {
	// Добавление комментария
	const addCommentButtons = document.querySelectorAll('.add-comment-btn');
	addCommentButtons.forEach(btn => {
		btn.addEventListener('click', function() {
			const articleId = this.dataset.articleId;
			const commentInput = this.previousElementSibling;
			const text = commentInput.value.trim();
			
			if (!text) {
				alert('Введите текст комментария');
				return;
			}
			
			fetch('/api/add-comment/', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-CSRFToken': getCookie('csrftoken')
				},
				body: JSON.stringify({
					article_id: articleId,
					text: text
				})
			})
			.then(response => response.json())
			.then(data => {
				if (data.success) {
					addCommentToDOM(articleId, data.comment);
					commentInput.value = '';
				} else {
					alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
				}
			})
			.catch(error => {
				console.error('Error:', error);
				alert('Произошла ошибка при добавлении комментария');
			});
		});
	});
	
	// Редактирование комментария
	document.addEventListener('click', function(e) {
		if (e.target.classList.contains('edit-comment-btn')) {
			const commentId = e.target.dataset.commentId;
			const commentItem = e.target.closest('.comment-item');
			const commentText = commentItem.querySelector('.comment-text');
			const currentText = commentText.textContent.trim();
			
			const newText = prompt('Редактировать комментарий:', currentText);
			if (newText && newText !== currentText) {
				fetch(`/api/edit-comment/${commentId}/`, {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						'X-CSRFToken': getCookie('csrftoken')
					},
					body: JSON.stringify({
						text: newText
					})
				})
				.then(response => response.json())
				.then(data => {
					if (data.success) {
						commentText.textContent = data.comment.text;
						const commentDate = commentItem.querySelector('.comment-date');
						commentDate.textContent = data.comment.created_at;
					} else {
						alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
					}
				})
				.catch(error => {
					console.error('Error:', error);
					alert('Произошла ошибка при редактировании комментария');
				});
			}
		}
	});
	
	// Удаление комментария
	document.addEventListener('click', function(e) {
		if (e.target.classList.contains('delete-comment-btn')) {
			if (!confirm('Вы уверены, что хотите удалить этот комментарий?')) {
				return;
			}
			
			const commentId = e.target.dataset.commentId;
			const commentItem = e.target.closest('.comment-item');
			
			fetch(`/api/delete-comment/${commentId}/`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-CSRFToken': getCookie('csrftoken')
				}
			})
			.then(response => response.json())
			.then(data => {
				if (data.success) {
					commentItem.remove();
					// Если комментариев не осталось, показываем сообщение
					const commentsList = commentItem.closest('.comments-list');
					if (commentsList && commentsList.querySelectorAll('.comment-item').length === 0) {
						const noComments = document.createElement('p');
						noComments.className = 'no-comments';
						noComments.textContent = 'Пока нет комментариев';
						commentsList.appendChild(noComments);
					}
				} else {
					alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
				}
			})
			.catch(error => {
				console.error('Error:', error);
				alert('Произошла ошибка при удалении комментария');
			});
		}
	});
}

// Добавление комментария в DOM
function addCommentToDOM(articleId, comment) {
	const commentsList = document.querySelector(`.comments-list[data-article-id="${articleId}"]`);
	
	// Удаляем сообщение "Пока нет комментариев"
	const noComments = commentsList.querySelector('.no-comments');
	if (noComments) {
		noComments.remove();
	}
	
	// Создаем новый элемент комментария
	const commentItem = document.createElement('div');
	commentItem.className = 'comment-item';
	commentItem.dataset.commentId = comment.id;
	commentItem.innerHTML = `
		<div class="comment-content">
			<p class="comment-text">${escapeHtml(comment.text)}</p>
			<span class="comment-date">${comment.created_at}</span>
		</div>
		<div class="comment-actions">
			<button class="edit-comment-btn" data-comment-id="${comment.id}">Редактировать</button>
			<button class="delete-comment-btn" data-comment-id="${comment.id}">Удалить</button>
		</div>
	`;
	
	commentsList.appendChild(commentItem);
}

// Вспомогательные функции
function getCookie(name) {
	let cookieValue = null;
	if (document.cookie && document.cookie !== '') {
		const cookies = document.cookie.split(';');
		for (let i = 0; i < cookies.length; i++) {
			const cookie = cookies[i].trim();
			if (cookie.substring(0, name.length + 1) === (name + '=')) {
				cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
				break;
			}
		}
	}
	return cookieValue;
}

function escapeHtml(text) {
	const map = {
		'&': '&amp;',
		'<': '&lt;',
		'>': '&gt;',
		'"': '&quot;',
		"'": '&#039;'
	};
	return text.replace(/[&<>"']/g, m => map[m]);
}
