package com.mercadez.dto;

import lombok.Getter;
import java.time.LocalDateTime;

@Getter
public class ErroResponse {
    private final int           status;
    private final String        erro;
    private final String        mensagem;
    private final LocalDateTime timestamp = LocalDateTime.now();

    public ErroResponse(int status, String erro, String mensagem) {
        this.status   = status;
        this.erro     = erro;
        this.mensagem = mensagem;
    }
}
