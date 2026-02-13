from typing import Dict, Any, List

from django.contrib.auth.models import User

from ..models import Reaction


class LocalReactionsClient:
    """
    Локальная реализация Reactions Service.

    Сейчас работает напрямую с Django‑моделью Reaction.
    В будущем может быть заменена на HTTP‑клиент к FastAPI‑сервису.
    """

    def toggle_reaction(
        self, user: User, article_url: str, reaction_type: str
    ) -> Dict[str, Any]:
        if not article_url or not reaction_type:
            return {
                "success": False,
                "error": "Не указаны обязательные параметры",
                "status": 400,
            }

        valid_types = [rt[0] for rt in Reaction.REACTION_TYPES]
        if reaction_type not in valid_types:
            return {
                "success": False,
                "error": "Неверный тип реакции",
                "status": 400,
            }

        reaction, created = Reaction.objects.get_or_create(
            user=user,
            article_url=article_url,
            defaults={"reaction_type": reaction_type},
        )

        if not created:
            if reaction.reaction_type == reaction_type:
                # Та же реакция — удаляем (отмена)
                reaction.delete()
                return {
                    "success": True,
                    "reaction_type": None,
                    "reactions_count": self._get_reactions_count(article_url),
                    "status": 200,
                }
            else:
                # Меняем тип реакции
                reaction.reaction_type = reaction_type
                reaction.save()

        return {
            "success": True,
            "reaction_type": reaction_type,
            "reactions_count": self._get_reactions_count(article_url),
            "status": 200,
        }

    def _get_reactions_count(self, article_url: str) -> Dict[str, int]:
        reactions = Reaction.objects.filter(article_url=article_url)
        count_dict: Dict[str, int] = {}
        for reaction_type, _ in Reaction.REACTION_TYPES:
            count = reactions.filter(reaction_type=reaction_type).count()
            if count > 0:
                count_dict[reaction_type] = count
        return count_dict

    def get_user_reactions_for_urls(
        self, user: User, urls: List[str]
    ) -> Dict[str, Any]:
        """
        Вернуть:
        - user_reactions: {url: reaction_type}
        - reactions_count: {url: {reaction_type: count}}
        для набора статей. Это используется на главной странице.
        """
        user_reactions_qs = Reaction.objects.filter(user=user, article_url__in=urls)
        user_reactions = {
            r.article_url: r.reaction_type for r in user_reactions_qs
        }

        reactions_count: Dict[str, Dict[str, int]] = {}
        for url in urls:
            if not url:
                continue
            reactions = Reaction.objects.filter(article_url=url)
            count_dict: Dict[str, int] = {}
            for reaction_type, _ in Reaction.REACTION_TYPES:
                count = reactions.filter(reaction_type=reaction_type).count()
                if count > 0:
                    count_dict[reaction_type] = count
            reactions_count[url] = count_dict

        return {
            "user_reactions": user_reactions,
            "reactions_count": reactions_count,
        }

