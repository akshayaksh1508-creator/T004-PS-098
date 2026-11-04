from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from validators import is_valid_cattle_type
from models import RateChart

def determine_milk_type(fat, declared_type):
    """
    Determines which rate chart should be used.

    Fat below 3.0 is rejected.
    Mixed milk always uses the Cow rate chart.
    Fat up to and including 5.0 uses the Cow chart.
    Fat above 5.0 uses the Buffalo chart.
    """

    fat = Decimal(str(fat))
    declared_type = declared_type.upper()

    if not is_valid_cattle_type(declared_type):
        raise ValueError("INVALID_CATTLE_TYPE")

    if fat < Decimal("3.0"):
        raise ValueError("FAT_TOO_LOW")

    if declared_type == "MIXED":
        return "COW"

    if fat <= Decimal("5.0"):
        return "COW"

    return "BUFFALO"


def get_rate_chart(milk_type):
    """
    Returns the rate chart for the selected milk type.
    Mixed milk uses the Cow rate chart.
    """

    milk_type = milk_type.upper()

    if milk_type == "MIXED":
        milk_type = "COW"

    if milk_type == "COW":
        return RateChart(
            milk_type="COW",
            base_fat=Decimal("3.5"),
            base_snf=Decimal("8.5"),
            base_price=Decimal("32.00"),
            fat_step_price=Decimal("0.60"),
            snf_step_price=Decimal("0.30")
        )

    elif milk_type == "BUFFALO":
        return RateChart(
            milk_type="BUFFALO",
            base_fat=Decimal("6.0"),
            base_snf=Decimal("9.0"),
            base_price=Decimal("48.00"),
            fat_step_price=Decimal("0.70"),
            snf_step_price=Decimal("0.20")
        )

    else:
        raise ValueError("INVALID_MILK_TYPE")

def interpolate(x, x1, y1, x2, y2):
    """Find a value between two known points."""
    return y1 + ((x - x1) / (x2 - x1)) * (y2 - y1)


def get_grid_price(chart, fat, snf):
    """Calculate the price at an exact 0.1 Fat/SNF chart point."""
    step = Decimal("0.1")

    fat_steps = (fat - chart.base_fat) / step
    snf_steps = (snf - chart.base_snf) / step

    return (
        chart.base_price
        + fat_steps * chart.fat_step_price
        + snf_steps * chart.snf_step_price
    )


def calculate_base_price(chart, fat, snf):
    """Calculate milk price using two-axis linear interpolation."""
    fat = Decimal(str(fat))
    snf = Decimal(str(snf))
    step = Decimal("0.1")

    lower_fat = chart.base_fat + (
        (fat - chart.base_fat) / step
    ).to_integral_value(rounding=ROUND_FLOOR) * step

    upper_fat = lower_fat + step

    lower_snf = chart.base_snf + (
        (snf - chart.base_snf) / step
    ).to_integral_value(rounding=ROUND_FLOOR) * step

    upper_snf = lower_snf + step

    # Interpolate along SNF at the lower Fat value
    price1 = interpolate(
        snf, lower_snf,
        get_grid_price(chart, lower_fat, lower_snf),
        upper_snf,
        get_grid_price(chart, lower_fat, upper_snf)
    )

    # Interpolate along SNF at the upper Fat value
    price2 = interpolate(
        snf, lower_snf,
        get_grid_price(chart, upper_fat, lower_snf),
        upper_snf,
        get_grid_price(chart, upper_fat, upper_snf)
    )

    # Interpolate between the two Fat values
    final_price = interpolate(
        fat, lower_fat, price1, upper_fat, price2
    )

    return final_price.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

