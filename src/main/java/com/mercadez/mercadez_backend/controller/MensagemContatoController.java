package com.mercadez.mercadez_backend.controller;

import com.mercadez.mercadez_backend.model.MensagemContato;
import com.mercadez.mercadez_backend.service.MensagemContatoService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/contato")
@CrossOrigin(origins = "*")
public class MensagemContatoController {

    private final MensagemContatoService service;

    public MensagemContatoController(MensagemContatoService service) {
        this.service = service;
    }

    @PostMapping
    public MensagemContato enviarMensagem(@RequestBody MensagemContato mensagem) {
        return service.salvar(mensagem);
    }
}
