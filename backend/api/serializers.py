from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import serializers

from recipes.models import Ingredient, IngredientInRecipe, Recipe, Tag
from .fields import Base64ImageField
from .mixins import SubscriptionMixin

User = get_user_model()


class UserAvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=True)

    class Meta:
        model = User
        fields = ['avatar']

    def update(self, instance, validated_data):
        instance.avatar = validated_data.get('avatar', instance.avatar)
        instance.save()
        return instance


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name']


class UserDetailSerializer(SubscriptionMixin, serializers.ModelSerializer):
    avatar = Base64ImageField(required=False)
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name',
            'last_name', 'avatar', 'is_subscribed'
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'email', 'id', 'username',
            'first_name', 'last_name', 'password'
        ]
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User(**validated_data)
        user.set_password(validated_data['password'])
        user.save()
        return user


class UserListSerializer(SubscriptionMixin, serializers.ModelSerializer):
    avatar = Base64ImageField(required=True)
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username',
            'first_name', 'last_name', 'avatar', 'is_subscribed'
        ]

    def update(self, instance, validated_data):
        super().update(instance, validated_data)

        if 'avatar' in validated_data:
            instance.avatar = validated_data.get('avatar', instance.avatar)

        instance.save()
        return instance


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = "__all__"


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id', read_only=True)
    name = serializers.CharField(source='ingredient.name', read_only=True)
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit', read_only=True)

    class Meta:
        model = IngredientInRecipe
        fields = ['id', 'name', 'measurement_unit', 'amount']


class RecipeListSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = UserDetailSerializer(read_only=True)
    ingredients = IngredientInRecipeSerializer(
        many=True, source='ingredientinrecipe'
    )
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = "__all__"

    def get_is_favorited(self, obj):
        return self._is_user_related(obj, 'favorites')

    def get_is_in_shopping_cart(self, obj):
        return self._is_user_related(obj, 'shopping_cart')

    def _is_user_related(self, obj, relation_name):
        user = self.context['request'].user
        if user.is_authenticated:
            return getattr(obj, relation_name).filter(user=user).exists()
        return False


class IngredientAmountSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField()

    class Meta:
        model = Ingredient
        fields = ['id', 'amount']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Количество ингредиента должно быть больше 0."
            )
        return value


class RecipeCreateSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True)
    author = UserDetailSerializer(read_only=True)
    ingredients = IngredientAmountSerializer(many=True)
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = "__all__"

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError(
                "Поле 'tags' не может быть пустым."
            )

        tag_ids = [tag.id for tag in value]
        if len(tag_ids) != len(set(tag_ids)):
            raise serializers.ValidationError("Теги не могут повторяться.")

        return value

    def validate_ingredients(self, ingredients):
        if not ingredients:
            raise serializers.ValidationError(
                "Добавьте хотя бы один ингредиент!"
            )

        ingredient_ids = []
        for ingredient in ingredients:
            if 'id' not in ingredient or 'amount' not in ingredient:
                raise serializers.ValidationError(
                    "Каждый ингредиент должен содержать 'id' и 'amount'."
                )

            ingredient_ids.append(ingredient['id'])

        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                "Рецепт не может включать два одинаковых ингредиента!"
            )

        return ingredients

    def validate_cooking_time(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Время приготовления должно быть не менее 1 минуты."
            )
        return value

    def _handle_ingredients(self, recipe, ingredients):
        ingredient_objects = []
        for ingredient in ingredients:
            amount = ingredient.get("amount")
            ingredient_id = ingredient.get("id")
            ingredient_instance = get_object_or_404(
                Ingredient, pk=ingredient_id.id
            )

            ingredient_objects.append(
                IngredientInRecipe(
                    recipe=recipe, ingredient=ingredient_instance,
                    amount=amount
                )
            )
        return ingredient_objects

    def create(self, validated_data):
        author = self.context.get("request").user
        tags = validated_data.pop("tags")
        ingredients = validated_data.pop("ingredients")

        recipe = Recipe.objects.create(author=author, **validated_data)
        recipe.tags.set(tags)

        ingredient_objects = self._handle_ingredients(recipe, ingredients)
        IngredientInRecipe.objects.bulk_create(ingredient_objects)

        return recipe

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        if tags is not None:
            instance.tags.set(tags)

        ingredients = validated_data.pop("ingredients", None)
        if ingredients is not None:
            instance.ingredients.clear()

            ingredient_objects = self._handle_ingredients(
                instance, ingredients
            )
            IngredientInRecipe.objects.bulk_create(ingredient_objects)

        return super().update(instance, validated_data)

    def to_representation(self, instance):
        serializer = RecipeListSerializer(
            instance, context={"request": self.context.get("request")}
        )

        return serializer.data


class RecipeSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ['id', 'name', 'image', 'cooking_time']


class SubscriptionSerializer(SubscriptionMixin, serializers.ModelSerializer):
    avatar = Base64ImageField(required=False)
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'avatar',
            'is_subscribed', 'recipes', 'recipes_count'
        ]

    def get_recipes(self, obj):
        recipes_limit = self.context.get('recipes_limit', None)
        recipes = Recipe.objects.filter(author=obj)
        if recipes_limit:
            recipes = recipes[:int(recipes_limit)]
        return RecipeSubscriptionSerializer(
            recipes, many=True, context=self.context).data

    def get_recipes_count(self, obj):
        return Recipe.objects.filter(author=obj).count()
