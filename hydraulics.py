def calculate_road_depth(feature, rain_intensity, duration_min, drain_factor):
    """
    Physical Rate-Balance Hydrology Model for Chennai:
    Compares the Rate of Rainfall (Inflow in L/sec) against
    the Rate of Storm Inlet Intake (Outflow in L/sec).
    """
    p = feature.get("properties", {})
    elev = max(1.0, float(p.get("elevation_msl", 4.0)))
    runoff_coeff = float(p.get("runoff_coeff", 0.75))

    # Catchment: 100m street section + rooftop runoff from adjacent plots
    catchment_area = 1200.0  # sq meters

    # 1. RAIN INFLOW RATE (Liters per second):
    # rain_intensity (mm/hr) / 3600 = mm/sec
    # 1 mm on 1 sqm = 1 Liter
    rain_rate_lps = (rain_intensity / 3600.0) * catchment_area
    runoff_rate_lps = rain_rate_lps * runoff_coeff

    # 2. DRAIN OUTFLOW RATE (Liters per second):
    # Roadside inlet grate / catchpit physical intake limits
    dia = int(p.get("pipe_dia_mm", 350))
    if dia >= 1200:
        base_intake_lps = 32.0   # Arterial RCC Box Culvert
    elif dia >= 900:
        base_intake_lps = 20.0   # Secondary road drain
    elif dia >= 600:
        base_intake_lps = 12.0   # Tertiary street drain
    else:
        base_intake_lps = 6.0    # Chhoti residential gali intake

    # Gravity & coastal backwater factor:
    # Low elevations (< 4m MSL) suffer severe gravity reduction & tidal locking
    if elev < 3.5:
        gravity_mult = 0.40
    elif elev < 6.5:
        gravity_mult = 0.75
    else:
        gravity_mult = 1.15

    actual_drain_rate_lps = base_intake_lps * drain_factor * gravity_mult

    # 3. RATE DEFICIT & NET STAGNATION:
    # Agar rain rate > drain rate, har second sadak par paani jama hota hai
    net_inflow_lps = max(0.0, runoff_rate_lps - actual_drain_rate_lps)

    # Total excess water after storm duration (in liters)
    storm_seconds = duration_min * 60.0
    accumulated_excess_liters = net_inflow_lps * storm_seconds

    # Depressional pooling in natural bowls (Velachery, Pallikaranai, Vyasarpadi)
    # Nichle ilaqo me aaju-baaju ka paani bhi beh kar aa jata hai
    pooling_mult = 1.0 + (1.8 / (elev ** 0.65))
    final_excess_liters = accumulated_excess_liters * pooling_mult

    # Convert liters to water column depth on street (cm)
    # 10 Liters on 1 sqm = 1 cm depth
    depth_cm = round((final_excess_liters / catchment_area) * 0.1, 1)

    return depth_cm
def calculate_road_depth(feature, rain_intensity, duration_min, drain_factor):
    p = feature.get("properties", {})
    elev = max(1.0, float(p.get("elevation_msl", 4.0)))
    runoff_coeff = float(p.get("runoff_coeff", 0.75))

    road_area = 1200.0  # sqm
    rain_rate_lps = (rain_intensity / 3600.0) * road_area
    runoff_rate_lps = rain_rate_lps * runoff_coeff

    dia = int(p.get("pipe_dia_mm", 350))
    if dia >= 1200:
        base_intake_lps = 32.0
    elif dia >= 900:
        base_intake_lps = 20.0
    elif dia >= 600:
        base_intake_lps = 12.0
    else:
        base_intake_lps = 6.0

    gravity_mult = 0.40 if elev < 3.5 else (0.75 if elev < 6.5 else 1.15)
    actual_drain_rate_lps = base_intake_lps * drain_factor * gravity_mult

    net_inflow_lps = max(0.0, runoff_rate_lps - actual_drain_rate_lps)
    storm_seconds = duration_min * 60.0
    accumulated_excess = net_inflow_lps * storm_seconds

    pooling_mult = 1.0 + (1.8 / (elev ** 0.65))
    final_excess_liters = accumulated_excess * pooling_mult

    return round((final_excess_liters / road_area) * 0.1, 1)