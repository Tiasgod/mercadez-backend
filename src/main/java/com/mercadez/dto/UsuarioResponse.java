package com.mercadez.dto;

import com.mercadez.model.Usuario;
import lombok.Data;
import java.time.LocalDateTime;

@Data
public class UsuarioResponse {
    private Long          id;
    private String        nome;
    private String        email;
    private String        cpf;
    private String        perfil;
    private LocalDateTime criadoEm;

    public static UsuarioResponse de(Usuario u) {
        var r = new UsuarioResponse();
        r.setId(u.getId());
        r.setNome(u.getNome());
        r.setEmail(u.getEmail());
        r.setCpf(u.getCpf());
        r.setPerfil(u.getPerfil().name());
        r.setCriadoEm(u.getCriadoEm());
        return r;
    }
}
