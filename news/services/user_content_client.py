from typing import List, Dict, Any, Set

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth.models import User

from ..models import FavoriteArticle, Comment


class LocalUserContentClient:
    """
    Локальная реализация User Content Service (избранное + комментарии).

    Сейчас работает напрямую с Django‑моделями.
    В будущем может быть заменена на HTTP‑клиент к FastAPI‑сервису.
    """

    # ----- Избранное -----

    def get_favorite_urls(self, user: User) -> Set[str]:
        return set(
            FavoriteArticle.objects.filter(user=user).values_list("url", flat=True)
        )

    def get_favorites_with_comments(self, user: User) -> List[Dict[str, Any]]:
        favorite_articles = FavoriteArticle.objects.filter(user=user)
        articles_with_comments: List[Dict[str, Any]] = []

        for article in favorite_articles:
            comments = Comment.objects.filter(article=article, user=user)
            articles_with_comments.append(
                {
                    "article": article,
                    "comments": comments,
                }
            )

        return articles_with_comments

    def toggle_favorite(self, user: User, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Поведение полностью совпадает с текущим toggle_favorite view.
        """
        from datetime import datetime

        article_url = payload.get("url")
        title = payload.get("title", "")
        description = payload.get("description", "")
        image_url = payload.get("urlToImage", "")
        source_name = payload.get("source", {}).get("name", "Lenta.ru")
        published_at_str = payload.get("publishedAt", "")

        if not article_url:
            return {
                "success": False,
                "error": "URL статьи не указан",
                "status": 400,
            }

        # Парсим дату публикации (копия логики из view)
        try:
            if published_at_str:
                if "T" in published_at_str:
                    published_at = datetime.fromisoformat(
                        published_at_str.replace("Z", "+00:00")
                    )
                else:
                    published_at = timezone.now()
            else:
                published_at = timezone.now()
            if timezone.is_naive(published_at):
                published_at = timezone.make_aware(published_at)
        except Exception:
            published_at = timezone.now()

        favorite, created = FavoriteArticle.objects.get_or_create(
            user=user,
            url=article_url,
            defaults={
                "title": title,
                "description": description,
                "image_url": image_url,
                "source_name": source_name,
                "published_at": published_at,
            },
        )

        if not created:
            favorite.delete()
            return {"success": True, "is_favorite": False, "status": 200}

        return {"success": True, "is_favorite": True, "status": 200}

    # ----- Комментарии -----

    def add_comment(
        self, user: User, article_id: int, text: str
    ) -> Dict[str, Any]:
        if not article_id or not text:
            return {
                "success": False,
                "error": "Не указаны обязательные параметры",
                "status": 400,
            }

        article = get_object_or_404(FavoriteArticle, id=article_id, user=user)

        comment = Comment.objects.create(article=article, user=user, text=text)

        return {
            "success": True,
            "status": 200,
            "comment": {
                "id": comment.id,
                "text": comment.text,
                "created_at": comment.created_at.strftime("%d.%m.%Y %H:%M"),
            },
        }

    def edit_comment(
        self, user: User, comment_id: int, text: str
    ) -> Dict[str, Any]:
        comment = get_object_or_404(Comment, id=comment_id, user=user)

        if not text:
            return {
                "success": False,
                "error": "Текст комментария не может быть пустым",
                "status": 400,
            }

        comment.text = text
        comment.save()

        return {
            "success": True,
            "status": 200,
            "comment": {
                "id": comment.id,
                "text": comment.text,
                "created_at": comment.created_at.strftime("%d.%m.%Y %H:%M"),
            },
        }

    def delete_comment(self, user: User, comment_id: int) -> Dict[str, Any]:
        comment = get_object_or_404(Comment, id=comment_id, user=user)
        comment.delete()
        return {"success": True, "status": 200}

