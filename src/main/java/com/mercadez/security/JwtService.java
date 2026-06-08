package com.mercadez.security;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

@Service
public class JwtService {

    private final SecretKey key;
    private final long      expiration;

    public JwtService(
            @Value("${mercadez.jwt.secret}") String secret,
            @Value("${mercadez.jwt.expiration}") long expiration) {
        this.key        = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.expiration = expiration;
    }

    /** Gera um token JWT com subject = email, claim perfil = "USUARIO" | "AFILIADO" */
    public String gerarToken(Long id, String email, String perfil) {
        return Jwts.builder()
                .subject(email)
                .claim("id",     id)
                .claim("perfil", perfil)
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + expiration))
                .signWith(key)
                .compact();
    }

    public String extrairEmail(String token) {
        return claims(token).getSubject();
    }

    public String extrairPerfil(String token) {
        return claims(token).get("perfil", String.class);
    }

    public Long extrairId(String token) {
        return claims(token).get("id", Long.class);
    }

    public boolean isValido(String token) {
        try {
            claims(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }

    private Claims claims(String token) {
        return Jwts.parser()
                .verifyWith(key)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }
}
