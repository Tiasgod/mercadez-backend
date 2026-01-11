# Etapa de build: Maven + Java 21
FROM maven:3.9.0-eclipse-temurin-21 AS build

# Diretório de trabalho dentro da imagem
WORKDIR /app

# Copia pom.xml e código-fonte
COPY pom.xml .
COPY src ./src

# Build do projeto (ignora testes para agilizar)
RUN mvn clean package -DskipTests

# Etapa final: apenas Java runtime para rodar o jar
FROM eclipse-temurin:21-jre

WORKDIR /app

# Copia o jar gerado da etapa de build
COPY --from=build /app/target/*.jar app.jar

# Comando para iniciar a aplicação
ENTRYPOINT ["java", "-jar", "app.jar"]
