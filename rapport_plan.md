> **Note de langue** — `CONVENTION.md` impose l'anglais partout dans le projet.
> Ce document est un rapport de travail personnel, pas de la documentation
> produit : la dérogation est délibérée.

# Le cycle de vie des tâches — ce que c'est, et pourquoi

Ce rapport documente la décision la plus structurante de cette itération : donner aux tâches
MRTA un **cycle de vie complet**, avec un état d'échec et un chien de garde de progrès, plutôt
que le simple `PENDING → ASSIGNED → DONE` d'origine.

---

## 1. Le problème : un interblocage d'allocation invisible

Avant cette itération, `FleetManager` connaissait trois états et une seule transition sortante :
un agent atteint la cible, la tâche passe `DONE`. Rien d'autre ne pouvait arriver à une tâche.

Considérons la séquence suivante, que **l'interface rend triviale à provoquer** — il suffit de
cliquer sur une case entourée d'obstacles :

1. Une tâche est créée sur une cible **inatteignable**.
2. `_allocate()` lui affecte l'agent 7. La tâche passe `ASSIGNED`.
3. `_allocate()` calcule à chaque tick l'ensemble des agents libres comme
   « tous les agents moins ceux qui portent une tâche `ASSIGNED` ». L'agent 7 en est exclu.
4. L'agent 7 ne peut jamais atteindre la cible, donc la tâche n'est jamais `DONE`, donc
   l'agent 7 n'est **jamais** rendu au pool.

La flotte vient de perdre un robot. Définitivement.

**Ce qui rend ce défaut pernicieux, c'est qu'il est silencieux.** La navigation continue de
fonctionner parfaitement : PIBT planifie, les agents évitent les collisions, la fenêtre est
fluide. L'agent 7 se contente de faire du surplace près de son mur, ce qui ressemble exactement
à un agent qui attend. Rien dans l'interface ne distingue « en attente » de « perdu ». Avec 20
agents et quelques clics malheureux, la flotte se vide progressivement sans qu'aucun message
d'erreur n'apparaisse jamais.

C'est le défaut B du plan. Il n'était pas visible avant parce que **aucun chemin MRTA n'était
exécutable** : `mrta/` ne contenait que des abstractions.

---

## 2. La réponse : deux gardes, à deux moments différents

### 2.1 La garde statique, à l'entrée (`_intake`)

Certaines cibles sont réfutables immédiatement, sans rien simuler : hors grille, ou occupée par
une entité bloquante. Ces tâches sont rejetées à l'admission, marquées `FAILED` et comptées.

C'est bon marché et sans faux positif. Mais ça ne couvre qu'une petite partie des cas : une
cible peut être parfaitement libre et néanmoins inatteignable (enclavée derrière un mur), ou le
devenir en cours de route (`appear_at`).

### 2.2 Le chien de garde dynamique (`_watchdog`)

Pour tout le reste, on aurait pu chercher à **prouver** l'accessibilité — un BFS depuis l'agent
vers la cible, avant d'affecter. C'est le réflexe naturel, et c'est une erreur, pour deux
raisons :

- **L'accessibilité n'est pas une propriété statique.** Le monde a des entités à `appear_at` :
  un couloir ouvert au tick 3 peut être muré au tick 12, et inversement. Une preuve calculée à
  l'affectation est périmée dès le tick suivant.
- **Ce serait dupliquer le planificateur.** PIBT sait déjà naviguer. Réimplémenter un test
  d'accessibilité à côté, c'est se garantir deux notions divergentes de « atteignable », avec
  une allocation qui refuse des tâches que le planificateur aurait su résoudre.

Donc on ne prouve rien. **On observe l'absence de progrès.**

Concrètement, chaque tâche `ASSIGNED` mémorise la meilleure distance de Manhattan jamais
atteinte par son porteur (`best_distance`) et le tick où ce record est tombé
(`last_improvement_step`). Si le record ne bouge plus pendant `patience` ticks, on en conclut
que **cet appariement-là** ne va nulle part :

- l'agent est **libéré** — il retourne immédiatement au pool ;
- `attempts` est incrémenté ;
- la tâche repasse `PENDING` et pourra être retentée par quelqu'un d'autre.

C'est important que ce soit l'appariement qui soit mis en cause, et pas la tâche : un agent
peut échouer parce qu'il était coincé dans un embouteillage à l'autre bout de la carte, alors
qu'un agent mieux placé y arriverait sans peine. On donne donc `max_attempts` chances à la
tâche, avec un porteur différent à chaque fois. Ce n'est qu'après les avoir épuisées qu'on
conclut que le problème vient de la **cible**, et que la tâche passe `FAILED`.

### 2.3 Pourquoi `patience` est un compromis, pas un réglage optimal

Un seuil temporel est nécessairement arbitraire. Trop court, on désassigne des agents qui
étaient simplement bloqués dans un bouchon temporaire — et on paie du churn de buts inutile.
Trop long, un agent reste immobilisé longtemps avant d'être récupéré.

Il n'y a pas de valeur juste, parce que la bonne valeur dépend de la densité d'agents : plus la
grille est saturée, plus les blocages transitoires sont longs et légitimes. `patience=12` est un
point de départ à ajuster empiriquement, pas une constante fondamentale. C'est exposé dans
`ScenarioConfig` précisément pour pouvoir en jouer.

---

## 3. Pourquoi le chien de garde vit dans `FleetManager`

`FleetManager` est **le seul composant qui voit une tâche vivre à travers les ticks**. Le
coordinateur, lui, reçoit un `DispatchIntent` par tick — un état absolu, complet, sans mémoire
de ce qui précède. C'est tout l'intérêt de ce DTO.

Mettre le chien de garde dans PIBT reviendrait à lui faire mémoriser « depuis combien de temps
cet agent poursuit ce but », c'est-à-dire à réintroduire de la **sémantique d'allocation** dans
le planificateur — exactement le couplage que le pipeline `DispatchIntent` avait supprimé. Le
coordinateur redeviendrait dépendant de qui lui donne ses buts.

La règle qui en découle : *la navigation décide où aller au prochain pas ; l'allocation décide
si poursuivre ce but a encore un sens.* Deux questions, deux composants.

---

## 4. Pourquoi échouer visiblement plutôt que jeter silencieusement

`_prune()` retire les tâches terminales de la liste vive — sinon elle croît sans borne. Mais
elle **incrémente `completed_count` et `failed_count`** au passage, et ces compteurs remontent
jusqu'à la sidebar.

C'était un choix conscient. La solution paresseuse aurait été de simplement supprimer les
tâches irréalisables. Elle aurait résolu la fuite d'agents tout en **recréant le défaut sous une
autre forme** : le travail disparaîtrait sans laisser de trace, et une cible mal choisie
produirait une flotte qui a l'air de bien tourner alors qu'elle jette la moitié de ce qu'on lui
demande.

Abandonner du travail silencieusement est pire que l'échouer bruyamment. Un compteur `failed`
qui monte est une information exploitable ; une tâche évaporée n'en est pas une.

---

## 5. L'éligibilité — une addition qui n'était pas au plan initial

Le choix d'une sélection d'agents à la souris a créé une contrainte nouvelle : « envoie **ces**
agents-là vers B ». Or `Allocator.allocate(pending, free, grid)` ne sait rien de la sélection,
et `RandomAllocator` pioche n'importe qui.

Deux endroits possibles pour la contrainte :

- **dans l'allocateur** — il faudrait alors modifier l'interface `Allocator`, et chaque
  allocateur futur devrait réimplémenter le filtrage. `KDTreeGreedyAllocator` inclus.
- **dans la demande** — `Task.eligible` porte l'ensemble des agents autorisés, et
  `FleetManager._allocate()` partitionne les tâches pendantes par classe d'éligibilité, appelant
  l'allocateur une fois par classe.

Le second a été retenu. La raison est une question de responsabilité : « qui a le droit de
prendre cette tâche » est une propriété de **ce qu'on demande**, pas de **la façon dont on
apparie**. L'allocateur répond à « lequel de ces agents-ci pour cette tâche-là » ; restreindre
la liste d'entrée ne change pas sa nature. Résultat : l'interface `Allocator` est intacte, et
`KDTreeGreedyAllocator` fonctionnera sans une ligne d'adaptation.

Les classes restreintes sont servies **avant** les tâches sans contrainte, sinon une tâche
libre pourrait s'emparer d'un agent que la sélection réservait.

*Coût assumé* : N appels à l'allocateur au lieu d'un — donc N reconstructions d'index KD-tree à
terme. En pratique, une classe par lot envoyé plus la classe libre : négligeable.

---

## 6. Ce que ça change, mesurable

Le correctif de priorités (défaut C), fait dans la même passe, a un effet chiffré sur le
benchmark existant :

```
sim_many_pibt.py --seeds 2, point de rupture (N* = plus grand N à 100 % de réussite)

              avant     après
  4x4          6         6
  5x5          9         9
  8x8         13        19
```

La démotion à `-inf` d'un agent arrivé à son but n'était jamais annulée. Un agent poussé hors de
son but par héritage de priorité restait classé dernier pour le reste de la partie. Sur les
instances denses — celles où les poussées sont fréquentes — ça coûtait cher. « Être à son but »
est un **état**, la démotion devait donc être réversible dès que l'état cesse d'être vrai.

---

## 7. Ce qui reste ouvert

**L'hystérésis, avant d'écrire `KDTreeGreedyAllocator`.** Un allocateur par distance voudra
naturellement voler des agents déjà en vol si un plus proche se libère. Aujourd'hui `_allocate()`
exclut les agents `ASSIGNED`, ce qui borne mécaniquement le churn de buts. Lever cette borne
réveille le défaut C sous une autre forme : des buts qui changent tous les ticks, des priorités
resemées en permanence, une dérive anti-famine qui n'a jamais le temps de s'accumuler. Il faudra
un seuil de gain minimal pour autoriser un vol, ou un verrou temporel après affectation.

**Il n'y a toujours aucune suite de tests.** Les vérifications de cette itération ont été faites
par scripts jetables. `ScriptedTaskSource` et les graines fixes ont été écrits pour rendre les
scénarios déterministes : c'est le socle si on veut en construire une.
