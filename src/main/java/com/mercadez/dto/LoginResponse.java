package com.mercadez.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class LoginResponse {
    private String token;
    private String tipo;
    private String perfil;
    private Long   id;
    private String nome;
    private String email;
}
