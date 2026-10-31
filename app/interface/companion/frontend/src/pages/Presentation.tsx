import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";

const FILM = "/assets/c8cede45891b351eefe713455640c3a7.mp4";
const POSTER = "/assets/img/poster.jpg";
const FRONT = "/assets/img/rendu-1.jpg";
const PORTS = "/assets/img/rendu-3.jpg";

/**
 * Présentation publique du produit, affichée tant qu'aucune session n'est
 * ouverte. Les visuels sont les rendus du boîtier livrés avec le site ; le film
 * est servi par la box. Aucune donnée inventée, aucune ressource distante.
 */
export function PresentationPage() {
  const { me } = useAuth();
  const [film, setFilm] = useState(false);
  const [filmError, setFilmError] = useState(false);
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    document.title = "Miles Companion — le cockpit local de la Miles Box";
  }, []);

  useEffect(() => {
    if (!film) return;
    const element = video.current;
    if (!element) return;
    const attempt = element.play();
    if (attempt && typeof attempt.catch === "function") {
      attempt.catch(() => setFilmError(true));
    }
  }, [film]);

  return (
    <main className="presentation">
      <header className="pres-top">
        <Link className="pres-brand" to="/" aria-label="Miles Companion, accueil">
          <img className="pres-logo" src="/assets/miles.svg" alt="" width={38} height={38} />
          <span>
            <strong>Miles Companion</strong>
            <small>cockpit local</small>
          </span>
        </Link>
        {me ? (
          <Link className="btn btn-quiet" to="/">
            <i className="ri-arrow-left-line" aria-hidden="true" />
            Retour au cockpit
          </Link>
        ) : (
          <Link className="btn btn-quiet" to="/connexion">
            <i className="ri-login-box-line" aria-hidden="true" />
            Se connecter
          </Link>
        )}
      </header>

      <section className="pres-hero" aria-labelledby="pres-titre">
        <div>
          <p className="eyebrow">Miles Box · site local</p>
          <h1 id="pres-titre">Votre assistant tient dans une boîte, chez vous.</h1>
          <p className="pres-lead">
            Miles Companion est le cockpit de la Miles Box : il lit les capteurs réels de la
            machine, garde la mémoire des missions et laisse l'assistant agir — sous
            confirmation, sans passer par un serveur distant.
          </p>
          <div className="pres-actions">
            <Link className="btn btn-primary btn-lg" to={me ? "/" : "/connexion"}>
              <i className="ri-door-open-line" aria-hidden="true" />
              Ouvrir le cockpit
            </Link>
            <a className="btn btn-ghost btn-lg" href="#pres-boitier">
              Voir la boîte
            </a>
          </div>
          <p className="pres-note">
            <i className="ri-shield-check-line" aria-hidden="true" />
            Aucune ressource distante · aucun compte public · aucune requête sortante
          </p>
        </div>

        <figure className="pres-figure">
          <div className="pres-shot">
            <img
              src={FRONT}
              alt="Rendu du boîtier Miles Box : bloc noir, grille perforée, objectif central, bouton d'alimentation et liseré lumineux cyan."
              width={1400}
              height={1100}
              decoding="async"
            />
          </div>
          <figcaption>
            Rendu du boîtier. Le cockpit tourne sur cette machine, pas ailleurs.
          </figcaption>
        </figure>
      </section>

      <section className="pres-section" aria-labelledby="pres-boitier" id="pres-boitier">
        <div className="pres-section-head">
          <p className="eyebrow">Le matériel</p>
          <h2 id="pres-boitier">Ce que vous branchez</h2>
        </div>
        <div className="pres-split">
          <figure className="pres-figure">
            <div className="pres-shot">
              <img
                src={PORTS}
                alt="Arrière du boîtier : ports USB-C, alimentation DC 12 V, Ethernet et HDMI mini, au-dessus d'une grille de ventilation."
                width={1200}
                height={1000}
                loading="lazy"
                decoding="async"
              />
            </div>
            <figcaption>Face arrière du boîtier.</figcaption>
          </figure>
          <ul className="pres-ports-list">
            <li>
              <strong>USB-C</strong>
              <span>Port USB-C, visible sur la face arrière.</span>
            </li>
            <li>
              <strong>Alimentation 12 V</strong>
              <span>Bloc d'alimentation externe, un seul câble.</span>
            </li>
            <li>
              <strong>Ethernet</strong>
              <span>Raccordement au réseau local ; l'écoute reste sur <code>127.0.0.1</code> par défaut.</span>
            </li>
            <li>
              <strong>HDMI mini</strong>
              <span>Sortie écran.</span>
            </li>
          </ul>
        </div>
        <p className="pres-footnote">
          L'étiquette au dos porte le QR d'appairage : un scan associe le téléphone, le compte
          reste celui créé sur la box.
        </p>
      </section>

      <section className="pres-section" aria-labelledby="pres-fonctions">
        <div className="pres-section-head">
          <p className="eyebrow">Ce que la box fait</p>
          <h2 id="pres-fonctions">Trois gestes, une seule boîte</h2>
        </div>
        <ol className="pres-list">
          <li>
            <span className="pres-index" aria-hidden="true">
              01
            </span>
            <div>
              <h3>Mesurer</h3>
              <p>
                Processeur, mémoire, disque, températures : chaque valeur est lue sur la
                machine. Un capteur absent affiche sa raison, jamais un chiffre inventé.
              </p>
            </div>
          </li>
          <li>
            <span className="pres-index" aria-hidden="true">
              02
            </span>
            <div>
              <h3>Se souvenir</h3>
              <p>
                Missions, routines et mémoire vivent dans une base locale. Le mode développeur
                ouvre les journaux et les détails techniques, jamais les secrets.
              </p>
            </div>
          </li>
          <li>
            <span className="pres-index" aria-hidden="true">
              03
            </span>
            <div>
              <h3>Agir</h3>
              <p>
                Une mission ne démarre qu'après confirmation explicite : le jeton est à usage
                unique et expire en soixante secondes. L'assistant propose, vous décidez.
              </p>
            </div>
          </li>
        </ol>
      </section>

      <section className="pres-section" aria-labelledby="pres-fiche">
        <div className="pres-section-head">
          <p className="eyebrow">La fiche</p>
          <h2 id="pres-fiche">Ce qui reste chez vous</h2>
        </div>
        <dl className="pres-spec">
          <div>
            <dt>Hébergement</dt>
            <dd>La box elle-même — aucun cloud, aucun hébergeur tiers.</dd>
          </div>
          <div>
            <dt>Écoute</dt>
            <dd>
              <code>127.0.0.1</code> par défaut ; l'ouverture au réseau local est une décision
              explicite, jamais un défaut.
            </dd>
          </div>
          <div>
            <dt>Comptes</dt>
            <dd>
              Créés sur la box. Deux administrateurs maximum ; les autres comptes restent
              utilisateurs.
            </dd>
          </div>
          <div>
            <dt>Accès IA</dt>
            <dd>
              Autorisés sur la box. L'interface n'affiche jamais la valeur d'un accès et ne
              reçoit jamais une clé.
            </dd>
          </div>
          <div>
            <dt>Appairage</dt>
            <dd>
              Le QR du boîtier associe un téléphone ; l'appareil reste visible et révocable par
              un administrateur.
            </dd>
          </div>
          <div>
            <dt>Ressources</dt>
            <dd>
              Polices, icônes et scripts servis localement ; la page ne charge rien depuis
              Internet.
            </dd>
          </div>
        </dl>
      </section>

      <section className="pres-section" aria-labelledby="pres-film">
        <div className="pres-section-head">
          <p className="eyebrow">Le film</p>
          <h2 id="pres-film">Quatorze secondes, sans son</h2>
        </div>
        <div className="pres-film">
          {film ? (
            <video
              ref={video}
              className="pres-film-video"
              src={FILM}
              poster={POSTER}
              controls
              playsInline
              muted
              preload="auto"
              onError={() => setFilmError(true)}
            />
          ) : (
            <button
              type="button"
              className="pres-film-poster"
              onClick={() => setFilm(true)}
              aria-label="Lire le film de lancement, quatorze secondes, sans son"
            >
              <img src={POSTER} alt="" width={1920} height={1080} loading="lazy" />
              <span className="pres-film-play" aria-hidden="true">
                <i className="ri-play-fill" />
              </span>
            </button>
          )}
          {filmError ? (
            <p className="pres-film-error" role="status">
              Le film n'a pas pu être lu sur cet appareil. Le télécharger ?{" "}
              <a href={FILM} download>
                fichier MP4
              </a>
            </p>
          ) : null}
          <p className="pres-footnote">
            Quatorze secondes, sans son. L'ouverture du site le joue une fois par session,
            toujours interruptible ; ici, il ne démarre qu'au clic. Sous « mouvement
            réduit », l'affiche seule reste.
          </p>
        </div>
      </section>

      <section className="pres-section" aria-labelledby="pres-demarrer">
        <div className="pres-section-head">
          <p className="eyebrow">Démarrer</p>
          <h2 id="pres-demarrer">Associer un téléphone</h2>
        </div>
        <ol className="pres-howto">
          <li>
            <span className="pres-index" aria-hidden="true">
              01
            </span>
            <h3>Générer le QR</h3>
            <p>Depuis la box, avec l'adresse du réseau local.</p>
            <code className="pres-code">
              python -m app.interface.companion.pairing qr --out box-qr.png
            </code>
          </li>
          <li>
            <span className="pres-index" aria-hidden="true">
              02
            </span>
            <h3>Le coller au dos</h3>
            <p>
              Avec l'appareil photo du téléphone. En <code>http</code> local, le navigateur
              interdit la caméra du site : celle du téléphone suffit.
            </p>
          </li>
          <li>
            <span className="pres-index" aria-hidden="true">
              03
            </span>
            <h3>Se connecter</h3>
            <p>
              Avec le compte créé sur la box. L'appairage associe l'appareil, il ne donne aucun
              accès à lui seul.
            </p>
            <Link className="btn btn-ghost" to="/connexion">
              Se connecter
            </Link>
          </li>
        </ol>
      </section>

      <footer className="pres-foot">
        <p>Miles Companion · Miles Box · site local, aucune ressource distante</p>
        <div className="pres-foot-links">
          <Link to="/connexion">Connexion</Link>
          <a href="#pres-fiche">Fiche technique</a>
        </div>
      </footer>
    </main>
  );
}
