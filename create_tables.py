from models import Base
from database import engine

if __name__ == "__main__":
    print("🔧 Criando tabelas no banco...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tabelas criadas com sucesso!")
