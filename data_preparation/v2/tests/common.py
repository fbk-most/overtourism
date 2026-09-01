
def atp_to_comuni(json_apt):
    id_to_apt = {}
    for apt, id_list in json_apt.items():
        for id_comune in id_list:
            # Trasformiamo in int e poi in stringa a 6 cifre: "22001" -> "022001"
            id_6_cifre = str(int(id_comune)).zfill(6)
            id_to_apt[id_6_cifre] = apt
    return id_to_apt


def random_rgb():
    import secrets
    r = secrets.randbelow(256)
    g = secrets.randbelow(256)
    b = secrets.randbelow(256)
    return (r, g, b)
