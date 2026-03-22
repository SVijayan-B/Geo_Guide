from __future__ import annotations

from typing import Any

from app.application.dto.travel import RecommendationRequestDTO
from app.models.trip import Trip
from app.services.currency_detection_service import CurrencyDetectionService
from app.services.currency_service import CurrencyService
from app.services.recommendation_service import RecommendationService

BASE_PRICE_CURRENCY = "INR"


class RecommendationUseCase:
    def __init__(self) -> None:
        self.recommender = RecommendationService()
        self.currency_detector = CurrencyDetectionService()
        self.currency_service = CurrencyService()

    def _safe_amount(self, value: Any) -> float | None:
        try:
            return float(value)
        except Exception:
            return None

    def _enrich_prices_with_currency(
        self,
        payload: dict | None,
        *,
        home_currency: str,
        destination_currency: str,
    ):
        if not isinstance(payload, dict):
            return payload

        recommendations = payload.get("recommendations")
        if isinstance(recommendations, list):
            for rec in recommendations:
                if not isinstance(rec, dict):
                    continue
                amount = self._safe_amount(rec.get("price"))
                if amount is None:
                    continue

                comparison = self.currency_service.compare_home_and_destination(
                    amount=amount,
                    source_currency=BASE_PRICE_CURRENCY,
                    home_currency=home_currency,
                    destination_currency=destination_currency,
                )
                rec["price"] = comparison.get("amount_in_destination")
                rec["price_currency"] = comparison.get("destination_currency")
                rec["price_home"] = comparison.get("amount_in_home")
                rec["home_currency"] = comparison.get("home_currency")

        plans = payload.get("plans")
        if isinstance(plans, list):
            for plan in plans:
                if not isinstance(plan, dict):
                    continue
                split = plan.get("budget_split")
                if not isinstance(split, dict):
                    continue

                split_local = {}
                split_home = {}
                for key, value in split.items():
                    amt = self._safe_amount(value)
                    if amt is None:
                        continue

                    comparison = self.currency_service.compare_home_and_destination(
                        amount=amt,
                        source_currency=BASE_PRICE_CURRENCY,
                        home_currency=home_currency,
                        destination_currency=destination_currency,
                    )
                    destination_amt = comparison.get("amount_in_destination")
                    home_amt = comparison.get("amount_in_home")

                    if destination_amt is not None:
                        split_local[key] = round(float(destination_amt), 2)
                    if home_amt is not None:
                        split_home[key] = round(float(home_amt), 2)

                if split_local:
                    plan["budget_split"] = split_local
                    plan["budget_currency"] = destination_currency
                if split_home:
                    plan["budget_split_home"] = split_home
                    plan["home_currency"] = home_currency

        payload["destination_currency"] = destination_currency
        payload["home_currency"] = home_currency
        payload["base_price_currency"] = BASE_PRICE_CURRENCY
        return payload

    def resolve_mode(self, *, mode: str, is_user_at_airport: bool, flight_delayed: bool) -> str:
        if is_user_at_airport and flight_delayed:
            return "delay_mode"
        return mode

    def recommendation_for_trip(self, *, trip: Trip, request: RecommendationRequestDTO) -> dict:
        resolved_mode = self.resolve_mode(
            mode=request.mode,
            is_user_at_airport=request.is_user_at_airport,
            flight_delayed=request.flight_delayed,
        )

        payload = self.recommender.recommend(
            mode=resolved_mode,
            origin=trip.origin,
            destination=trip.destination,
            days=request.days,
            budget=request.budget,
            traveler_type=request.traveler_type,
            user_lat=request.user_lat,
            user_lon=request.user_lon,
        )

        home_currency_norm = self.currency_detector.detect_home_currency(request.home_currency)
        currency_anchor_city = trip.origin if resolved_mode in ("pre_trip_plan", "delay_mode") else trip.destination
        destination_currency_norm = self.currency_detector.detect_destination_currency(
            currency_anchor_city,
            fallback=BASE_PRICE_CURRENCY,
        )

        enriched = self._enrich_prices_with_currency(
            payload,
            home_currency=home_currency_norm,
            destination_currency=destination_currency_norm,
        )

        return {
            "trip_id": str(trip.id),
            "destination": trip.destination,
            "mode": resolved_mode,
            "budget": request.budget,
            "traveler_type": request.traveler_type,
            "home_currency": home_currency_norm,
            "destination_currency": destination_currency_norm,
            "currency_anchor_city": currency_anchor_city,
            **(enriched or {}),
        }
