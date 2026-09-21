"""Orchestrateur : exécute les 3 ETL dans l'ordre."""
import logging
import load_olist, load_retailrocket, load_churn

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    for module in (load_olist, load_retailrocket, load_churn):
        print(f"\n=== {module.__name__} ===")
        module.main()
    print("\nETL terminé. Vérifiez les volumes avec sql/99_controles.sql")
