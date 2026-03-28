def logg_inn():
    """
    Logger inn med garth OAuth-tokens fra miljøvariabler.
    Bruker aldri passord-innlogging for å unngå rate limiting.
    """
    import garth
    import json

    garth.configure(domain="garmin.com")
    client = garth.client

    # Forsøk 1: OAuth-tokens fra GitHub Secrets
    oauth1_json = os.environ.get("GARMIN_OAUTH1")
    oauth2_json = os.environ.get("GARMIN_OAUTH2")

    if oauth1_json and oauth2_json:
        try:
            from garth.auth_tokens import OAuth1Token, OAuth2Token
            client.oauth1_token = OAuth1Token(**json.loads(oauth1_json))
            client.oauth2_token = OAuth2Token(**json.loads(oauth2_json))
            api = Garmin()
            api.garth = client
            # Test at tokenet fungerer
            api.get_full_name()
            print("Innlogget med OAuth-tokens fra miljøvariabler")
            return api
        except Exception as e:
            print(f"OAuth-token feilet: {e}")

    # Forsøk 2: Lagret token lokalt (kun Mac)
    if os.path.exists(TOKENSTI):
        try:
            api = Garmin()
            api.login(TOKENSTI)
            print("Innlogget med lagret token")
            return api
        except Exception as e:
            print(f"Lagret token ugyldig: {e}")

    raise Exception("Ingen gyldige tokens tilgjengelig. Sett GARMIN_OAUTH1 og GARMIN_OAUTH2 i GitHub Secrets.")
