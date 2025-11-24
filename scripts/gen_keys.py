import secrets
from cryptography.fernet import Fernet

def tok(n=32): return secrets.token_urlsafe(n)

def main():
    print("SECRET_KEY=", secrets.token_hex(32))
    print("FERNET_KEY=", Fernet.generate_key().decode())
    kiosks = {"comb1": tok(), "photon1": tok(), "profile1": tok(), "elevate1": tok(), "logic1": tok(), "meltdown1": tok(), "chef1": tok(), "spectrum1": tok(), "bopit1": tok(), "twister1": tok()}
    games = {"rz_combination": tok(), "rz_photon": tok(), "rz_elevate": tok(), "rz_logic": tok(), "rz_meltdown": tok(), "rz_chef": tok(), "rz_spectrum": tok(), "rz_bopit": tok(), "rz_twister": tok()}
    print("KIOSK_KEYS=", ",".join(f"{k}:{v}" for k,v in kiosks.items()))
    print("GAME_KEYS=", ",".join(f"{k}:{v}" for k,v in games.items()))
if __name__ == "__main__":
    main()
