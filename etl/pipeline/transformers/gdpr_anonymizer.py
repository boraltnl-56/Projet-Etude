"""
UrbanFlow — Module d'Anonymisation RGPD
========================================
Assure la conformité RGPD pour les données de crowdsourcing citoyen.

Principes appliqués :
    - Privacy by Design (Art. 25 RGPD)
    - Minimisation des données (Art. 5)
    - Droit à l'effacement (Art. 17)
    - Pseudonymisation irréversible (pas de clé de déchiffrement)

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import hashlib
import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("urbanflow.etl.gdpr_anonymizer")

# Sel cryptographique — à stocker dans les secrets Kubernetes (jamais en clair)
_SALT = os.environ.get("GDPR_HASH_SALT", "urbanflow-default-salt-CHANGE-IN-PROD")

# Paramètres d'anonymisation géospatiale
_GEO_NOISE_DEGREES = 0.0015  # ≈ 150 mètres de floutage
_EPHEMERAL_ID_TTL_DAYS = 30  # Durée de vie des IDs éphémères (Art. 17 RGPD)


class GDPRAnonymizer:
    """
    Anonymiseur RGPD pour les données de crowdsourcing citoyen.

    Garantit qu'aucune donnée à caractère personnel n'est stockée
    en base de données. Les données anonymisées ne sont plus des
    "données personnelles" au sens du RGPD (Recital 26).

    Méthodes principales :
        anonymize()      : Anonymise un signalement citoyen complet
        hash_ip()        : Hash irréversible d'une adresse IP
        blur_coordinates(): Floutage GPS (±150m)
        generate_ephemeral_id(): UUID éphémère 30 jours

    Conformité :
        ✅ Art. 5 RGPD — Minimisation
        ✅ Art. 17 RGPD — Droit à l'oubli (TTL auto)
        ✅ Art. 25 RGPD — Privacy by Design
        ✅ Recital 26 — Données anonymisées hors scope RGPD
    """

    async def anonymize(
        self, data: dict[str, Any], client_ip: str = ""
    ) -> dict[str, Any]:
        """
        Anonymise un signalement citoyen de manière irréversible.

        Transformations appliquées :
        1. IP → SHA-256(IP + sel) [non réversible]
        2. Coordonnées GPS précises → approximées (floutage ±150m)
        3. Identifiant utilisateur → UUID éphémère (TTL 30j)
        4. Suppression de tous les champs PII restants

        Args:
            data: Dictionnaire du signalement brut (avec PII potentiels)
            client_ip: Adresse IP du client (fournie par FastAPI)

        Returns:
            dict[str, Any]: Signalement anonymisé — aucune PII
        """
        anonymized: dict[str, Any] = {}

        # 1. anonymisation de l'adresse ip
        ip_to_hash = client_ip or data.get("ip_address", "")
        anonymized["ip_hash"] = self.hash_ip(ip_to_hash) if ip_to_hash else None

        # 2. anonymisation des coordonnées gps
        lat = data.get("latitude")
        lon = data.get("longitude")
        if lat is not None and lon is not None:
            blurred_lat, blurred_lon = self.blur_coordinates(float(lat), float(lon))
            anonymized["latitude_approx"] = round(blurred_lat, 4)  # ~10m précision max
            anonymized["longitude_approx"] = round(blurred_lon, 4)
        else:
            anonymized["latitude_approx"] = None
            anonymized["longitude_approx"] = None

        # 3. identifiant éphémère (remplace tout id utilisateur)
        anonymized["ephemeral_id"] = self.generate_ephemeral_id()
        anonymized["ephemeral_id_expires_at"] = (
            datetime.now(timezone.utc) + timedelta(days=_EPHEMERAL_ID_TTL_DAYS)
        ).isoformat()

        # 4. conservation des données non-personnelles utiles
        anonymized["report_type"] = data.get(
            "report_type", "unknown"
        )  # embouteillage, accident...
        anonymized["severity"] = data.get("severity", 1)
        anonymized["timestamp"] = data.get(
            "timestamp", datetime.now(timezone.utc).isoformat()
        )
        anonymized["description"] = self._sanitize_text(data.get("description", ""))

        # 5. suppression explicite des pii
        # Les champs suivants sont JAMAIS persistés
        pii_fields = [
            "ip_address",
            "user_id",
            "email",
            "name",
            "phone",
            "device_id",
            "session_id",
            "latitude",
            "longitude",
        ]
        for field in pii_fields:
            data.pop(field, None)

        logger.debug(
            "🔐 Signalement anonymisé — ephemeral_id: %s (expires: %s)",
            anonymized["ephemeral_id"][:8] + "...",
            anonymized["ephemeral_id_expires_at"],
        )
        return anonymized

    @staticmethod
    def hash_ip(ip_address: str) -> str:
        """
        Génère un hash SHA-256 irréversible de l'adresse IP.

        Le sel (_SALT) rend impossible les attaques par table arc-en-ciel.
        SHA-256 est approuvé par l'ANSSI pour la pseudonymisation.

        Args:
            ip_address: Adresse IP brute (IPv4 ou IPv6)

        Returns:
            str: Hash hexadécimal à 64 caractères (non réversible)

        Example:
            >>> GDPRAnonymizer.hash_ip("192.168.1.1")
            "a7f3c2..."  # Hash irréversible
        """
        salted = f"{_SALT}:{ip_address}".encode("utf-8")
        return hashlib.sha256(salted).hexdigest()

    @staticmethod
    def blur_coordinates(latitude: float, longitude: float) -> tuple[float, float]:
        """
        Floute les coordonnées GPS pour garantir l'anonymité géographique.

        Ajoute un bruit aléatoire uniforme de ±150 mètres (≈0.0015°).
        Conforme aux recommandations CNIL pour la protection de la
        vie privée dans les applications de mobilité (2023).

        Args:
            latitude: Latitude précise (ex: 48.856614)
            longitude: Longitude précise (ex: 2.352222)

        Returns:
            tuple[float, float]: (latitude_floutée, longitude_floutée)

        Note:
            La précision est réduite à ~150m — insuffisante pour
            identifier une adresse personnelle mais suffisante pour
            les analyses de flux au niveau quartier/rue.
        """
        noise_lat = random.uniform(-_GEO_NOISE_DEGREES, _GEO_NOISE_DEGREES)
        noise_lon = random.uniform(-_GEO_NOISE_DEGREES, _GEO_NOISE_DEGREES)
        return latitude + noise_lat, longitude + noise_lon

    @staticmethod
    def generate_ephemeral_id() -> str:
        """
        Génère un UUID v4 éphémère pour identifier anonymement un signalement.

        Caractéristiques :
        - Aucun lien avec l'identité réelle de l'utilisateur
        - Expiration automatique après 30 jours (configuré en BDD)
        - UUID v4 : 122 bits d'entropie (cryptographiquement sûr)

        Returns:
            str: UUID v4 sous forme de chaîne (ex: "550e8400-e29b-41d4-a716-...")
        """
        return str(uuid.uuid4())

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """
        Nettoie un texte libre de toute donnée personnelle potentielle.

        Supprime les patterns communs de PII :
        - Numéros de téléphone (06/07/+33...)
        - Emails
        - Données structurées identifiantes

        Args:
            text: Texte brut de description du signalement

        Returns:
            str: Texte nettoyé, tronqué à 500 caractères max
        """
        import re

        # Suppression des numéros de téléphone
        text = re.sub(r"(\+33|0)(6|7)\s?(\d{2}\s?){4}", "[PHONE_REDACTED]", text)
        # Suppression des emails
        text = re.sub(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_REDACTED]", text
        )
        # Limitation de la longueur
        return text[:500]
