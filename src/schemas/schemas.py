from pydantic import BaseModel, EmailStr, HttpUrl, constr, conint
from typing import List, Optional


class Message(BaseModel):
    message: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=6)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    role: str

    model_config = {
        "from_attributes": True,
    }


class ProductBase(BaseModel):
    title: str
    description: str
    price: float
    category: str
    image_url: HttpUrl


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    price: Optional[float]
    category: Optional[str]
    image_url: Optional[HttpUrl]


class ProductRead(ProductBase):
    id: int

    model_config = {
        "from_attributes": True,
    }


class ProductList(BaseModel):
    total: int
    page: int
    limit: int
    data: List[ProductRead]


class CartItemCreate(BaseModel):
    product_id: int
    quantity: conint(gt=0) = 1


class CartProduct(BaseModel):
    id: int
    title: str
    price: float
    image_url: HttpUrl

    model_config = {
        "from_attributes": True,
    }


class CartItemRead(BaseModel):
    product: CartProduct
    quantity: int
    subtotal: float


class OrderItemRead(BaseModel):
    product: CartProduct
    quantity: int
    price: float


class OrderRead(BaseModel):
    id: int
    total: float
    items: List[OrderItemRead]

    model_config = {
        "from_attributes": True,
    }


class ReviewCreate(BaseModel):
    rating: conint(ge=1, le=5)
    comment: constr(min_length=1)


class ReviewRead(BaseModel):
    id: int
    user_id: int
    product_id: int
    rating: int
    comment: str

    model_config = {
        "from_attributes": True,
    }
