# Use Java 21 + Maven
FROM maven:3.9.0-eclipse-temurin-21 AS build

# Define diretório de trabalho
WORKDIR /app

# Copia os arquivos do projeto
COPY pom.xml .
COPY src ./src

# Build do projeto
RUN mvn clean package -DskipTests

# Imagem final apenas com Java para rodar o jar
FROM eclipse-temurin:21-jre

WORKDIR /app

# Copia o jar gerado na imagem de build
COPY --from=build /app/target/*.jar app.jar

# Comando para rodar a aplicação
ENTRYPOINT ["java", "-jar", "app.jar"]
