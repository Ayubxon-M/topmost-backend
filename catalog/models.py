from django.db import models


class City(models.Model):
    name = models.CharField("Shahar nomi", max_length=100)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField("Kategoriya", max_length=100)

    def __str__(self):
        return self.name


class Provider(models.Model):
    name = models.CharField("Ism / Do'kon nomi", max_length=150)
    phone = models.CharField("Telefon", max_length=20)
    telegram_username = models.CharField("Telegram username", max_length=100, blank=True)
    city = models.ForeignKey(City, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)

    def __str__(self):
        return self.name


class Listing(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    title = models.CharField("Sarlavha", max_length=200)
    description = models.TextField("Izoh", blank=True)
    price = models.PositiveIntegerField("Narx (so'm)", null=True, blank=True)
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField("Rasm", upload_to='listings/')
    order = models.PositiveSmallIntegerField("Tartib", default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.listing.title} - rasm {self.order}"
