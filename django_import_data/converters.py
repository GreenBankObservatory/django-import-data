def handle_sectors(sectors):
    a, b, c = sectors.split(" ")
    return {"sector_a": a, "sector_b": b, "sector_c": c}


def handle_dms(latitude, longitude):
    lat_d, lat_m, lat_s = latitude.split(" ")
    long_d, long_m, long_s = longitude.split(" ")
    return {
        "lat_d": lat_d,
        "lat_m": lat_m,
        "lat_s": lat_s,
        "long_d": long_d,
        "long_m": long_m,
        "long_s": long_s,
    }


def handle_location(latitude, longitude):
    return (latitude, longitude)


def handle_person(gender, name):
    title = "Mr." if gender == "male" else "Mrs."
    first_name, middle_name, last_name = name.split(" ")
    return {
        "title": title,
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
    }


def make_uppercase(value):
    return value.upper()
