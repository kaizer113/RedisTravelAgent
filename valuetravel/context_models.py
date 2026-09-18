from context_surfaces.context_model import ContextField, ContextModel


class Traveler(ContextModel):
    __redis_key_template__ = "value-travel:context:traveler:{member_id}"
    member_id: str = ContextField(
        is_key_component=True, description="Signed-in synthetic traveler ID"
    )
    name: str = ContextField(description="name", index="text")
    tier: str = ContextField(description="tier", index="tag")
    home_airport: str = ContextField(description="home airport", index="tag")
    household: str = ContextField(description="household", index="text")


class Offer(ContextModel):
    __redis_key_template__ = "value-travel:context:offer:{package_id}"
    package_id: str = ContextField(description="package id", is_key_component=True)
    name: str = ContextField(description="name", index="text")
    destination: str = ContextField(description="destination", index="tag")
    total_price: float = ContextField(description="total price", index="numeric")
    room_capacity: int = ContextField(
        description="Number of people accommodated by this offer", index="numeric"
    )
    average_price_per_person: float = ContextField(
        description="RDI-derived total_price divided by room_capacity, rounded to two decimal places",
        index="numeric",
    )
    available_rooms: int = ContextField(description="available rooms", index="numeric")
    eligible_reward_base: float = ContextField(
        description="eligible reward base", index="numeric"
    )
    cancellation: str = ContextField(description="cancellation", index="text")
    departure_date: str = ContextField(description="departure date", index="tag")
    data_label: str = ContextField(description="data label", index="tag")


class Reservation(ContextModel):
    __redis_key_template__ = "value-travel:context:reservation:{reservation_id}"
    reservation_id: str = ContextField(
        description="reservation id", is_key_component=True
    )
    member_id: str = ContextField(description="member id", index="tag")
    package_id: str = ContextField(description="package id", index="tag")
    status: str = ContextField(description="status", index="tag")
    departure_date: str = ContextField(description="departure date", index="tag")
    balance_due: float = ContextField(description="balance due", index="numeric")
    notes: str = ContextField(description="notes", index="text")
