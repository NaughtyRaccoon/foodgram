from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from rest_framework.views import APIView

from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from djoser import views as djoser_views
from djoser.serializers import SetPasswordSerializer

from .serializers import (
    UserSerializer, UserCreateSerializer, UserDetailSerializer,
    UserListSerializer, UserAvatarSerializer, RecipeCreateSerializer,
    TagSerializer, IngredientSerializer, RecipeListSerializer,
    SubscriptionSerializer, RecipeSubscriptionSerializer
)
from recipes.models import (
    Recipe, Tag, Ingredient, IngredientInRecipe, Favorite, ShoppingCart
)
from users.models import Subscription
from api.permissions import IsAuthor
from api.pagination import CustomPagination

User  = get_user_model()


class UserViewSet(djoser_views.UserViewSet):
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    pagination_class = CustomPagination
    permission_classes = [permissions.AllowAny]

    def get_permissions(self):
        if self.action == 'list':
            return [permissions.AllowAny()]
        elif self.action in ['me', 'update_avatar']:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            if self.action == 'list':
                return UserListSerializer
            elif self.action == 'subscriptions':
                return SubscriptionSerializer
            return UserDetailSerializer
        elif self.request.method == 'POST':
            if self.action == 'subscribe':
                return SubscriptionSerializer
            elif self.action == 'change_password':
                return SetPasswordSerializer
            return UserCreateSerializer
        elif self.request.method in ['PUT', 'PATCH']:
            return UserDetailSerializer
        return UserDetailSerializer
    
    @action(detail=False, methods=['post'], url_path='set_password')
    def change_password(self, request):

        serializer = SetPasswordSerializer(
            request.user, data=request.data, context={'request': request})

        if serializer.is_valid():
            request.user.set_password(
                serializer.validated_data['new_password'])
            request.user.save()
            return Response(
                {"detail": "Пароль успешно изменён."},
                status=status.HTTP_204_NO_CONTENT
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(
        detail=False, methods=['get'],
        permission_classes=[permissions.IsAuthenticatedOrReadOnly]
    )
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(
        detail=False, methods=['get'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def subscriptions(self, request):
        subscriptions = request.user.subscriptions.all().order_by('id')
        recipes_limit = request.query_params.get('recipes_limit', None)
        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(subscriptions, request)

        results = []
        for subscription in result_page:
            user_data = SubscriptionSerializer(
                subscription.subscribed_to, context={'request': request,
                'recipes_limit': recipes_limit}).data
            results.append(user_data)

        return paginator.get_paginated_response(results)

    @action(
        detail=True, methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def subscribe(self, request, id=None):
        user_to_subscribe = get_object_or_404(User, id=id)

        if user_to_subscribe == request.user:
            return Response(
                {'detail': 'Нельзя подписаться на самого себя.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.method == 'POST':
            if Subscription.objects.filter(
                user=request.user, subscribed_to=user_to_subscribe).exists():
                return Response(
                    {'detail': 'Вы уже подписаны на этого пользователя.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            Subscription.objects.create(
                user=request.user, subscribed_to=user_to_subscribe)
            recipes_limit = request.query_params.get('recipes_limit', None)
            user_data = SubscriptionSerializer(
                user_to_subscribe, context={'request': request,
                'recipes_limit': recipes_limit}).data
            return Response(user_data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            subscription = Subscription.objects.filter(
                user=request.user, subscribed_to=user_to_subscribe)
            if not subscription.exists():
                return Response(
                    {'detail': 'Вы не подписаны на этого пользователя.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
 

class UserAvatarView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        user = request.user
        serializer = UserAvatarSerializer(user, data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"avatar": request.build_absolute_uri(user.avatar.url)},
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        user = request.user
        user.avatar.delete(save=False)
        user.avatar = None
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer

class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name', None)
        if name:
            queryset = queryset.filter(name__startswith=name)
        return queryset


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all().order_by('id')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action in ['shopping_cart', 'favorite']:
            return RecipeSubscriptionSerializer
        elif self.request.method in ['POST', 'PATCH']:
            return RecipeCreateSerializer
        return RecipeListSerializer
    
    def get_permissions(self):
        if self.action in ['shopping_cart', 'favorite']:
            self.permission_classes = [permissions.IsAuthenticated]
        elif self.request.method in ['PATCH', 'DELETE']:
            self.permission_classes = [IsAuthor]
        return super().get_permissions()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        is_favorited = self.request.query_params.get('is_favorited', None)
        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart', None)
        author_id = self.request.query_params.get('author', None)
        tags = self.request.query_params.getlist('tags')

        if is_favorited == '1' and user.is_authenticated:
            queryset = queryset.filter(favorites__user=user)

        if is_in_shopping_cart == '1' and user.is_authenticated:
            queryset = queryset.filter(shopping_cart__user=user)

        if author_id:
            queryset = queryset.filter(author_id=author_id)

        if tags:
            queryset = queryset.filter(tags__slug__in=tags).distinct()

        return queryset
    
    @action(detail=True, methods=['get'], url_path='get-link')
    def get_link(self, request, pk=None):
        try:
            recipe = self.get_object()
            short_link = f"https://foodgram.example.org/s/{recipe.id}"
            return Response(
                {'short-link': short_link}, status=status.HTTP_200_OK
            )
        except Recipe.DoesNotExist:
            return Response(
                {'detail': 'Страница не найдена.'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(
        detail=False, methods=['get'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        user = request.user
        ingredients = IngredientInRecipe.objects.filter(
            recipe__shopping_cart__user=user
        ).values(
            'ingredient__name', 'ingredient__measurement_unit'
        ).order_by(
            'ingredient__name'
        ).annotate(ingredient_total=Sum('amount'))

        purchased_in_file = ""
        for ingredient in ingredients:
            purchased_in_file += (
                f"{ingredient['ingredient__name']} - "
                f"{ingredient['ingredient_total']} "
                f"{ingredient['ingredient__measurement_unit']}\n"
            )
        response = HttpResponse(purchased_in_file, content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename="shopping_cart.txt"'
        )
        return response

    @action(
        detail=True, methods=["post", "delete"], url_path="shopping_cart",
        url_name="shopping_cart"
    )
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()

        if request.method == "POST":
            if ShoppingCart.objects.filter(
                user=request.user, recipe=recipe).exists():
                return Response(
                    {"detail": "Рецепт уже есть в списке покупок."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            ShoppingCart.objects.get_or_create(
                user=request.user, recipe=recipe)
            serializer = self.get_serializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == "DELETE":
            shopping_cart_item = ShoppingCart.objects.filter(
                user=request.user, recipe=recipe)
            if shopping_cart_item.exists():
                shopping_cart_item.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response(
                    {"detail": "Рецепт не найден в корзине."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(
        detail=True, methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated], url_path='favorite'
    )
    def favorite(self, request, pk=None):
        recipe = self.get_object()

        if request.method == 'POST':
            if Favorite.objects.filter(
                user=request.user, recipe=recipe).exists():
                return Response(
                    {"detail": "Recipe already in favorites."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            Favorite.objects.create(user=request.user, recipe=recipe)
            serializer = self.get_serializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            favorite_item = Favorite.objects.filter(
                user=request.user, recipe=recipe)
            if favorite_item.exists():
                favorite_item.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response(
                    {"detail": "Рецепт не найден в избранном."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
