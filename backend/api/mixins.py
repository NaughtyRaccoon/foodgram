from rest_framework.response import Response
from rest_framework import status

from users.models import Subscription


class SubscriptionMixin:
    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Subscription.objects.filter(
                user=request.user, subscribed_to=obj).exists()
        return False


class RecipeActionMixin:
    def handle_recipe_action(self, request, recipe, model, action):
        exists = model.objects.filter(
            user=request.user, recipe=recipe
        ).exists()

        if action == 'add':
            if exists:
                return Response(
                    {"detail": "Рецепт уже есть в списке."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            model.objects.create(user=request.user, recipe=recipe)
            serializer = self.get_serializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif action == 'remove':
            if exists:
                model.objects.filter(user=request.user, recipe=recipe).delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(
                {"detail": "Рецепт не найден."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
