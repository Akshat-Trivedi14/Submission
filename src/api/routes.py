from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from src.core.security import (
    admin_only,
    create_access_token,
    get_current_user,
    get_db,
    get_password_hash,
    verify_password,
)
from src.models.models import CartItem, Order, OrderItem, Product, Review, User, Wishlist
from src.schemas.schemas import (
    CartItemCreate,
    CartItemRead,
    Message,
    OrderRead,
    ProductCreate,
    ProductList,
    ProductRead,
    ProductUpdate,
    ReviewCreate,
    ReviewRead,
    Token,
    UserCreate,
)

router = APIRouter()

request_log: Dict[str, List[float]] = {}


@router.get("/", response_model=Message)
def root():
    return {"message": "E-Commerce Backend is running"}


def rate_limiter(request: Request, max_requests: int = 40, window_seconds: int = 60):
    ip = request.client.host if request.client else "unknown"
    import time

    now = time.time()
    history = request_log.get(ip, [])
    history = [timestamp for timestamp in history if now - timestamp < window_seconds]
    if len(history) >= max_requests:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
    history.append(now)
    request_log[ip] = history


@router.post("/signup", response_model=Message, status_code=status.HTTP_201_CREATED)
def signup(user_create: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_create.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    role = "admin" if user_create.email == "admin@example.com" else "user"
    user = User(email=user_create.email, password=get_password_hash(user_create.password), role=role)
    db.add(user)
    db.commit()
    return {"message": "User created successfully"}


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"id": user.id})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/products", response_model=ProductRead, dependencies=[Depends(rate_limiter)])
def create_product(
    product_in: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    product = Product(**product_in.dict())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/products", response_model=ProductList, dependencies=[Depends(rate_limiter)])
def get_products(
    search: Optional[str] = Query(None, description="Search by product title"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort: Optional[str] = Query(None, pattern="^(asc|desc)$", description="Sort by price"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Product)
    if search:
        query = query.filter(Product.title.ilike(f"%{search}%"))
    if category:
        query = query.filter(Product.category == category)
    if sort == "asc":
        query = query.order_by(Product.price.asc())
    elif sort == "desc":
        query = query.order_by(Product.price.desc())

    total = query.count()
    offset = (page - 1) * limit
    products = query.offset(offset).limit(limit).all()
    return {"total": total, "page": page, "limit": limit, "data": products}


@router.get("/products/{product_id}", response_model=ProductRead, dependencies=[Depends(rate_limiter)])
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.put("/products/{product_id}", response_model=ProductRead, dependencies=[Depends(rate_limiter)])
def update_product(
    product_id: int,
    product_updates: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    for field, value in product_updates.dict(exclude_unset=True).items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", response_model=Message, dependencies=[Depends(rate_limiter)])
def delete_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    db.delete(product)
    db.commit()
    return {"message": "Product deleted"}


@router.post("/cart/items", response_model=Message, dependencies=[Depends(rate_limiter)])
def add_to_cart(
    item: CartItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(Product.id == item.product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    cart_item = db.query(CartItem).filter_by(user_id=user.id, product_id=item.product_id).first()
    if cart_item:
        cart_item.quantity += item.quantity
    else:
        cart_item = CartItem(user_id=user.id, product_id=item.product_id, quantity=item.quantity)
        db.add(cart_item)

    db.commit()
    return {"message": "Item added to cart"}


@router.get("/cart", response_model=List[CartItemRead], dependencies=[Depends(rate_limiter)])
def get_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cart_items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
    response: list[CartItemRead] = []
    for item in cart_items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            continue
        response.append(
            CartItemRead(
                product=product,
                quantity=item.quantity,
                subtotal=round(product.price * item.quantity, 2),
            )
        )
    return response


@router.put("/cart/items/{product_id}", response_model=Message, dependencies=[Depends(rate_limiter)])
def update_cart_item(
    product_id: int,
    item: CartItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cart_item = db.query(CartItem).filter_by(user_id=user.id, product_id=product_id).first()
    if not cart_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    cart_item.quantity = item.quantity
    db.commit()
    return {"message": "Cart item updated"}


@router.delete("/cart/items/{product_id}", response_model=Message, dependencies=[Depends(rate_limiter)])
def remove_cart_item(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cart_item = db.query(CartItem).filter_by(user_id=user.id, product_id=product_id).first()
    if not cart_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    db.delete(cart_item)
    db.commit()
    return {"message": "Cart item removed"}


@router.post("/orders", response_model=OrderRead, dependencies=[Depends(rate_limiter)])
def create_order(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cart_items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
    if not cart_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    total = 0.0
    for cart_item in cart_items:
        product = db.query(Product).filter(Product.id == cart_item.product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart contains deleted product")
        total += product.price * cart_item.quantity

    order = Order(user_id=user.id, total=round(total, 2))
    db.add(order)
    db.commit()
    db.refresh(order)

    order_items: list[OrderItem] = []
    for cart_item in cart_items:
        product = db.query(Product).filter(Product.id == cart_item.product_id).first()
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=cart_item.quantity,
            price=product.price,
        )
        db.add(order_item)
        order_items.append(order_item)

    db.query(CartItem).filter(CartItem.user_id == user.id).delete()
    db.commit()

    return OrderRead(
        id=order.id,
        total=order.total,
        items=[
            OrderItemRead(product=db.query(Product).filter(Product.id == item.product_id).first(), quantity=item.quantity, price=item.price)
            for item in order_items
        ],
    )


@router.get("/orders", response_model=List[OrderRead], dependencies=[Depends(rate_limiter)])
def get_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    orders = db.query(Order).filter(Order.user_id == user.id).all()
    result: list[OrderRead] = []
    for order in orders:
        order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        items = [
            OrderItemRead(
                product=db.query(Product).filter(Product.id == item.product_id).first(),
                quantity=item.quantity,
                price=item.price,
            )
            for item in order_items
        ]
        result.append(OrderRead(id=order.id, total=order.total, items=items))
    return result


@router.post("/wishlist/{product_id}", response_model=Message, dependencies=[Depends(rate_limiter)])
def add_to_wishlist(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    existing = db.query(Wishlist).filter_by(user_id=user.id, product_id=product_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product already in wishlist")

    db.add(Wishlist(user_id=user.id, product_id=product_id))
    db.commit()
    return {"message": "Added to wishlist"}


@router.get("/wishlist", response_model=List[ProductRead], dependencies=[Depends(rate_limiter)])
def get_wishlist(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.query(Wishlist).filter(Wishlist.user_id == user.id).all()
    product_ids = [item.product_id for item in items]
    if not product_ids:
        return []
    return db.query(Product).filter(Product.id.in_(product_ids)).all()


@router.post("/reviews/{product_id}", response_model=ReviewRead, dependencies=[Depends(rate_limiter)])
def add_review(product_id: int, review: ReviewCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    review_model = Review(
        user_id=user.id,
        product_id=product_id,
        rating=review.rating,
        comment=review.comment,
    )
    db.add(review_model)
    db.commit()
    db.refresh(review_model)
    return review_model


@router.get("/reviews/{product_id}", response_model=List[ReviewRead], dependencies=[Depends(rate_limiter)])
def get_reviews(product_id: int, db: Session = Depends(get_db)):
    return db.query(Review).filter(Review.product_id == product_id).all()
